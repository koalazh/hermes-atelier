(function () {
  "use strict";

  var sdk = window.__HERMES_PLUGIN_SDK__;
  var registry = window.__HERMES_PLUGINS__;
  if (!sdk || !registry) return;

  var React = sdk.React;
  var h = React.createElement;
  var useState = sdk.hooks.useState;
  var useEffect = sdk.hooks.useEffect;
  var useCallback = sdk.hooks.useCallback;
  var API = "/api/plugins/atelier";

  function json(path, init) {
    return sdk.fetchJSON(API + path, init || {});
  }

  function post(path, body) {
    return json(path, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  function Button(props) {
    return h(
      "button",
      {
        className: "atelier-button " + (props.kind || ""),
        disabled: props.disabled,
        onClick: props.onClick,
        type: props.type || "button",
      },
      props.children,
    );
  }

  function Badge(props) {
    return h("span", { className: "atelier-badge " + (props.value || "") }, props.value || "—");
  }

  function Empty(props) {
    return h("div", { className: "atelier-empty" }, props.children);
  }

  function ErrorBox(props) {
    return props.error ? h("div", { className: "atelier-error" }, String(props.error)) : null;
  }

  function useApps() {
    var state = useState([]);
    var apps = state[0];
    var setApps = state[1];
    var reload = useCallback(function () {
      return json("/apps").then(function (value) {
        setApps(value.items || []);
        return value.items || [];
      });
    }, []);
    useEffect(function () {
      reload().catch(function () {});
    }, [reload]);
    return [apps, reload];
  }

  function BuildView(props) {
    var requestState = useState("");
    var request = requestState[0];
    var setRequest = requestState[1];
    var buildState = useState(null);
    var build = buildState[0];
    var setBuild = buildState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];

    useEffect(
      function () {
        if (!build || ["approved", "builder_failed", "profile_install_failed"].indexOf(build.status) >= 0) return;
        var timer = setInterval(function () {
          json("/builds/" + build.id)
            .then(setBuild)
            .catch(function (value) { setError(value.message); });
        }, 1200);
        return function () { clearInterval(timer); };
      },
      [build && build.id, build && build.status],
    );

    function create() {
      setBusy(true);
      setError("");
      post("/builds", { request: request })
        .then(setBuild)
        .catch(function (value) { setError(value.message); })
        .finally(function () { setBusy(false); });
    }

    function approve() {
      if (!build) return;
      setBusy(true);
      post("/builds/" + build.id + "/approve")
        .then(function (value) {
          setBuild(value.build);
          props.reloadApps();
        })
        .catch(function (value) { setError(value.message); })
        .finally(function () { setBusy(false); });
    }

    return h("div", { className: "atelier-grid two" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "INTENT → PROFILES"),
        h("h2", null, "Build an Agent application"),
        h("p", { className: "muted" }, "Describe the business outcome. Builder investigates and proposes the smallest justified Profile set; it cannot approve its own work."),
        h("textarea", {
          className: "atelier-textarea tall",
          value: request,
          placeholder: "Who uses this application, what inputs exist, what outcome is expected, and which real systems are available?",
          onChange: function (event) { setRequest(event.target.value); },
        }),
        h("div", { className: "actions" },
          h(Button, { disabled: busy || !request.trim(), onClick: create }, busy ? "Starting…" : "Start Builder"),
        ),
        h(ErrorBox, { error: error }),
      ),
      h("section", { className: "atelier-card contract" },
        h("div", { className: "row spread" },
          h("div", null, h("div", { className: "eyebrow" }, "BUILD CONTRACT"), h("h2", null, build ? "Draft " + build.id.slice(0, 8) : "No active draft")),
          build ? h(Badge, { value: build.status }) : null,
        ),
        build
          ? h(React.Fragment, null,
              h("pre", { className: "atelier-document" }, build.build_contract || "Waiting for Builder…"),
              build.builder_output ? h("details", null, h("summary", null, "Builder output"), h("pre", { className: "atelier-output" }, build.builder_output)) : null,
              build.last_error ? h(ErrorBox, { error: build.last_error }) : null,
              build.status === "awaiting_approval"
                ? h("div", { className: "approval" },
                    h("strong", null, "Explicit approval boundary"),
                    h("p", null, "Approval promotes this draft, installs native Hermes Distributions, creates runtime-only endpoints, and starts Profile Gateways."),
                    h(Button, { kind: "primary", disabled: busy, onClick: approve }, "Approve & install"),
                  )
                : null,
            )
          : h(Empty, null, "BUILD.md will appear here after you start Builder."),
      ),
    );
  }

  function AppsView(props) {
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    function act(appId, action) {
      setError("");
      post("/apps/" + appId + "/" + action)
        .then(props.reload)
        .catch(function (value) { setError(value.message); });
    }
    return h("div", null,
      h("div", { className: "section-heading" }, h("div", null, h("div", { className: "eyebrow" }, "VERSIONED APPLICATIONS"), h("h2", null, "Apps")), h(Button, { onClick: props.reload }, "Refresh")),
      h(ErrorBox, { error: error }),
      props.apps.length
        ? h("div", { className: "atelier-grid cards" }, props.apps.map(function (app) {
            return h("section", { className: "atelier-card app-card", key: app.id },
              h("div", { className: "row spread" }, h("div", null, h("h3", null, app.display_name), h("code", null, app.id)), h("span", { className: "revision" }, app.definition_revision)),
              h("dl", { className: "meta" }, h("dt", null, "Entry"), h("dd", null, app.entry_profile), h("dt", null, "Profiles"), h("dd", null, String((app.endpoints || []).length))),
              h("div", { className: "endpoint-list" }, (app.endpoints || []).map(function (endpoint) {
                return h("div", { className: "endpoint", key: endpoint.profile },
                  h("div", null,
                    h("strong", null, endpoint.profile),
                    h("small", null, endpoint.host + ":" + endpoint.port),
                    endpoint.missing_environment && endpoint.missing_environment.length
                      ? h("small", { className: "missing-env" }, "Missing: " + endpoint.missing_environment.join(", "))
                      : null,
                  ),
                  h(Badge, { value: endpoint.status }),
                );
              })),
              h("div", { className: "actions" },
                h(Button, { onClick: function () { act(app.id, "start"); } }, "Start"),
                h(Button, { onClick: function () { act(app.id, "restart"); } }, "Restart"),
                h(Button, { kind: "danger", onClick: function () { act(app.id, "stop"); } }, "Stop"),
                h("a", { className: "native-link", href: "/profiles" }, "Open native Profiles ↗"),
              ),
            );
          }))
        : h(Empty, null, "No registered applications. Build one or run bootstrap."),
    );
  }

  function streamRun(runId, onEvent) {
    return sdk.authedFetch(API + "/runs/" + runId + "/events").then(function (response) {
      if (!response.ok || !response.body) throw new Error("Unable to stream Run events");
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      function read() {
        return reader.read().then(function (chunk) {
          if (chunk.done) return;
          buffer += decoder.decode(chunk.value, { stream: true });
          var frames = buffer.split("\n\n");
          buffer = frames.pop();
          frames.forEach(function (frame) {
            var data = frame.split("\n").find(function (line) { return line.indexOf("data:") === 0; });
            if (!data) return;
            try { onEvent(JSON.parse(data.slice(5).trim())); } catch (_) {}
          });
          return read();
        });
      }
      return read();
    });
  }

  function SpanTree(props) {
    var spans = props.spans || [];
    var byParent = {};
    spans.forEach(function (span) {
      var key = span.parent_span_id || "root";
      (byParent[key] || (byParent[key] = [])).push(span);
    });
    function branch(parent, depth) {
      return (byParent[parent] || []).map(function (span) {
        return h("div", { key: span.id },
          h("div", { className: "span", style: { marginLeft: depth * 18 + "px" } },
            h("span", { className: "span-line" }),
            h("div", null, h("strong", null, span.source_profile + " → " + span.target_profile), h("small", null, span.target_hermes_run_id || "waiting for Hermes Run")),
            h(Badge, { value: span.status }),
          ),
          branch(span.id, depth + 1),
        );
      });
    }
    return spans.length ? h("div", { className: "span-tree" }, branch("root", 0)) : h(Empty, null, "The entry Agent has not called a specialist." );
  }

  function PlaygroundView(props) {
    var appState = useState("");
    var appId = appState[0];
    var setAppId = appState[1];
    var inputState = useState("");
    var input = inputState[0];
    var setInput = inputState[1];
    var scenarioState = useState("");
    var scenarioId = scenarioState[0];
    var setScenarioId = scenarioState[1];
    var scenariosState = useState([]);
    var scenarios = scenariosState[0];
    var setScenarios = scenariosState[1];
    var memoryState = useState(null);
    var memoryScope = memoryState[0];
    var setMemoryScope = memoryState[1];
    var runState = useState(null);
    var run = runState[0];
    var setRun = runState[1];
    var eventsState = useState([]);
    var events = eventsState[0];
    var setEvents = eventsState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    useEffect(function () { if (!appId && props.apps[0]) setAppId(props.apps[0].id); }, [props.apps.length]);
    useEffect(function () {
      if (!appId) return;
      json("/apps/" + appId).then(function (value) {
        setScenarios(value.scenarios || []);
        setScenarioId("");
        setMemoryScope(null);
      });
    }, [appId]);

    function chooseScenario(value) {
      setScenarioId(value);
      var selected = scenarios.find(function (scenario) { return scenario.id === value; });
      if (selected) {
        setInput(selected.input);
        setMemoryScope(selected.memory_scope || null);
      }
    }

    function refresh(id) {
      return json("/runs/" + id).then(setRun);
    }
    function start() {
      setError(""); setEvents([]);
      post("/runs", { app_id: appId, input: input, scenario_id: scenarioId || null, memory_scope: memoryScope, user_label: "Playground" })
        .then(function (created) {
          setRun(created);
          streamRun(created.id, function (event) {
            if (event.event_type) setEvents(function (existing) { return existing.concat([event]); });
          }).then(function () { refresh(created.id); });
        })
        .catch(function (value) { setError(value.message); });
    }
    function stop() { if (run) post("/runs/" + run.id + "/stop").then(function () { refresh(run.id); }); }
    function replay() { if (run) post("/runs/" + run.id + "/replay").then(function (value) { setRun(value.replay); setEvents([]); streamRun(value.replay.id, function (event) { if (event.event_type) setEvents(function (old) { return old.concat([event]); }); }).then(function () { refresh(value.replay.id); }); }); }
    function feedback(outcome) { if (run) post("/runs/" + run.id + "/feedback", { outcome: outcome, feedback: "Marked in Playground" }).then(function () { refresh(run.id); }); }

    return h("div", { className: "atelier-grid playground" },
      h("section", { className: "atelier-card composer" },
        h("div", { className: "eyebrow" }, "REAL HERMES EXECUTION"), h("h2", null, "Playground"),
        h("label", null, "Application"),
        h("select", { className: "atelier-input", value: appId, onChange: function (event) { setAppId(event.target.value); } }, props.apps.map(function (app) { return h("option", { value: app.id, key: app.id }, app.display_name); })),
        h("label", null, "Saved scenario (optional)"),
        h("select", { className: "atelier-input", value: scenarioId, onChange: function (event) { chooseScenario(event.target.value); } },
          h("option", { value: "" }, "Temporary request"),
          scenarios.map(function (scenario) { return h("option", { value: scenario.id, key: scenario.id }, scenario.name); }),
        ),
        h("label", null, "Request or acceptance scenario"),
        h("textarea", { className: "atelier-textarea tall", value: input, onChange: function (event) { setInput(event.target.value); }, placeholder: "Give the entry Agent a complete outcome, not a route." }),
        h("div", { className: "actions" }, h(Button, { kind: "primary", disabled: !appId || !input.trim(), onClick: start }, "Run"), run && ["queued", "running", "stopping"].indexOf(run.status) >= 0 ? h(Button, { kind: "danger", onClick: stop }, "Request stop") : null, run ? h(Button, { onClick: replay }, "Replay") : null),
        h(ErrorBox, { error: error }),
        run ? h("div", { className: "feedback" }, h("span", null, "Human result"), ["success", "partial", "failure"].map(function (value) { return h(Button, { key: value, onClick: function () { feedback(value); } }, value); })) : null,
      ),
      h("section", { className: "atelier-card trace" },
        h("div", { className: "row spread" }, h("div", null, h("div", { className: "eyebrow" }, "ATELIER RUN"), h("h2", null, run ? run.id.slice(0, 12) : "Waiting")), run ? h(Badge, { value: run.status }) : null),
        run ? h(React.Fragment, null,
          h("div", { className: "root-run" }, h("strong", null, run.root_profile), h("code", null, run.root_hermes_run_id || "Hermes Run pending")),
          h(SpanTree, { spans: run.spans }),
          h("h3", null, "Live evidence"),
          h("div", { className: "event-list" }, events.slice(-80).map(function (event) { return h("div", { className: "event", key: event.id }, h("code", null, event.event_type), h("span", null, event.profile)); })),
          run.output_text ? h("pre", { className: "atelier-output" }, run.output_text) : null,
        ) : h(Empty, null, "Run output, real Hermes IDs, and cross-Profile Spans appear here.")),
    );
  }

  function ReviewView(props) {
    var runsState = useState([]);
    var runs = runsState[0];
    var setRuns = runsState[1];
    var selectedState = useState([]);
    var selected = selectedState[0];
    var setSelected = selectedState[1];
    var reviewState = useState(null);
    var review = reviewState[0];
    var setReview = reviewState[1];
    var proposalState = useState(null);
    var proposal = proposalState[0];
    var setProposal = proposalState[1];
    var feedbackState = useState("");
    var feedback = feedbackState[0];
    var setFeedback = feedbackState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    useEffect(function () { json("/runs").then(function (value) { setRuns(value.items || []); }); }, []);
    useEffect(function () {
      if (!review || ["completed", "review_failed"].indexOf(review.status) >= 0) return;
      var timer = setInterval(function () { json("/reviews/" + review.id).then(setReview); }, 1200);
      return function () { clearInterval(timer); };
    }, [review && review.id, review && review.status]);
    useEffect(function () {
      if (!proposal || ["pending", "proposal_invalid", "applied", "rejected", "reverted"].indexOf(proposal.status) >= 0) return;
      var timer = setInterval(function () { json("/proposals/" + proposal.id).then(setProposal); }, 1200);
      return function () { clearInterval(timer); };
    }, [proposal && proposal.id, proposal && proposal.status]);
    function toggle(id) { setSelected(function (values) { return values.indexOf(id) >= 0 ? values.filter(function (value) { return value !== id; }) : values.concat([id]); }); }
    function createReview() {
      var first = runs.find(function (run) { return selected.indexOf(run.id) >= 0; });
      if (!first) return;
      post("/reviews", { app_id: first.app_id, run_ids: selected, feedback: feedback }).then(setReview).catch(function (value) { setError(value.message); });
    }
    function createProposal() { post("/reviews/" + review.id + "/proposals").then(setProposal).catch(function (value) { setError(value.message); }); }
    function proposalAction(action) { post("/proposals/" + proposal.id + "/" + action).then(function (value) { setProposal(value.proposal || value); }).catch(function (value) { setError(value.message); }); }
    return h("div", { className: "atelier-grid review-grid" },
      h("section", { className: "atelier-card" }, h("div", { className: "eyebrow" }, "FROZEN TRACE BUNDLE"), h("h2", null, "Select evidence"),
        h("div", { className: "run-picker" }, runs.map(function (run) { return h("label", { className: "run-choice", key: run.id }, h("input", { type: "checkbox", checked: selected.indexOf(run.id) >= 0, onChange: function () { toggle(run.id); } }), h("div", null, h("strong", null, run.app_id + " / " + run.id.slice(0, 8)), h("small", null, run.status)), h(Badge, { value: run.status })); })),
        h("textarea", { className: "atelier-textarea", value: feedback, onChange: function (event) { setFeedback(event.target.value); }, placeholder: "Human expectation or observed gap" }),
        h(Button, { kind: "primary", disabled: !selected.length, onClick: createReview }, "Run independent Reviewer"), h(ErrorBox, { error: error })),
      h("section", { className: "atelier-card" }, h("div", { className: "row spread" }, h("div", null, h("div", { className: "eyebrow" }, "EVIDENCE → HYPOTHESIS"), h("h2", null, "Review")), review ? h(Badge, { value: review.status }) : null),
        review && review.result ? h("pre", { className: "atelier-document" }, review.result) : h(Empty, null, "Reviewer observations and uncertainty appear here."),
        review && review.status === "completed" ? h(Button, { onClick: createProposal }, "Ask Builder for candidate patch") : null),
      h("section", { className: "atelier-card proposal-card" }, h("div", { className: "row spread" }, h("div", null, h("div", { className: "eyebrow" }, "HUMAN APPROVAL"), h("h2", null, "Proposal & replay")), proposal ? h(Badge, { value: proposal.status }) : null),
        proposal && proposal.patch ? h("pre", { className: "atelier-diff" }, proposal.patch) : h(Empty, null, "A path-validated full diff appears here. Reviewer cannot apply it."),
        proposal && proposal.status === "pending" ? h("div", { className: "actions" }, h(Button, { kind: "primary", onClick: function () { proposalAction("apply"); } }, "Approve & apply"), h(Button, { kind: "danger", onClick: function () { proposalAction("reject"); } }, "Reject")) : null,
        proposal && proposal.status === "applied" ? h("div", { className: "actions" }, h(Button, { onClick: function () { proposalAction("revert"); } }, "Revert candidate"), selected[0] ? h(Button, { kind: "primary", onClick: function () { post("/runs/" + selected[0] + "/replay"); } }, "Replay same scenario") : null) : null),
    );
  }

  function AtelierApp() {
    var tabState = useState("Build");
    var tab = tabState[0];
    var setTab = tabState[1];
    var appHook = useApps();
    var apps = appHook[0];
    var reloadApps = appHook[1];
    var tabs = ["Build", "Apps", "Playground", "Review"];
    var content = tab === "Build" ? h(BuildView, { reloadApps: reloadApps }) : tab === "Apps" ? h(AppsView, { apps: apps, reload: reloadApps }) : tab === "Playground" ? h(PlaygroundView, { apps: apps }) : h(ReviewView, { apps: apps });
    return h("main", { className: "atelier-shell" },
      h("header", { className: "atelier-hero" }, h("div", null, h("div", { className: "mark" }, "HA"), h("div", null, h("h1", null, "Hermes Atelier"), h("p", null, "Intent into Profiles. Collaboration into evidence. Changes under human control.")))),
      h("nav", { className: "atelier-tabs" }, tabs.map(function (name) { return h("button", { key: name, className: tab === name ? "active" : "", onClick: function () { setTab(name); } }, name); })),
      h("div", { className: "atelier-content" }, content),
    );
  }

  registry.register("atelier", AtelierApp);
})();
