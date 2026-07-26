(function () {
  "use strict";

  var sdk = window.__HERMES_PLUGIN_SDK__;
  var registry = window.__HERMES_PLUGINS__;
  if (!sdk || !registry) return;
  var React = sdk.React;
  var h = React.createElement;
  var useState = sdk.hooks.useState;
  var useEffect = sdk.hooks.useEffect;
  var API = "/api/plugins/atelier";

  function json(path, init) { return sdk.fetchJSON(API + path, init || {}); }
  function post(path, body) {
    return json(path, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  }
  function Button(props) {
    return h("button", {
      className: "atelier-button " + (props.kind || ""),
      disabled: props.disabled,
      onClick: props.onClick,
    }, props.children);
  }
  function Badge(props) {
    return h("span", { className: "atelier-badge " + (props.value || "") }, props.value || "—");
  }
  function ErrorBox(props) {
    return props.error ? h("div", { className: "atelier-error" }, String(props.error)) : null;
  }
  function Empty(props) {
    return h("div", { className: "atelier-empty" }, props.children);
  }
  function Evidence(props) {
    var levels = props.levels || ["packed"];
    return h("div", { className: "evidence-ladder" }, levels.map(function (level) {
      return h(Badge, { key: level, value: level });
    }));
  }
  function download(name, content) {
    var url = URL.createObjectURL(new Blob([content], { type: "text/markdown" }));
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function Overview(props) {
    var pack = props.workspace.pack;
    var instances = props.workspace.instances || [];
    return h("div", { className: "atelier-grid two" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "ATELIER CORE"),
        h("h2", null, pack.id + " workspace"),
        h("p", null, "Design → Coding Agent Handoff → Native Hermes Run → App Pack → HTTP Delivery"),
        h("dl", { className: "meta" },
          h("dt", null, "Entry"), h("dd", null, pack.entry),
          h("dt", null, "Agents"), h("dd", null, String(Object.keys(pack.agents || {}).length)),
          h("dt", null, "State"), h("dd", null, pack.state_policy),
          h("dt", null, "Calls"), h("dd", null, Object.keys(pack.allowed_calls || {}).length ? "profile_call Tool Policy" : "No declared calls")),
        h("p", { className: "muted" }, "The Pack declares structure. Hermes owns runtime behavior, Sessions, Memory, models, tools, and collaboration.")),
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "DISCOVERED LOCALLY"),
        h("h2", null, "Instances and evidence"),
        instances.length ? instances.map(function (item) {
          return h("div", { className: "root-run", key: item.instance },
            h("div", null, h("strong", null, item.instance), h("small", null, item.entry_profile)),
            h(Evidence, { levels: item.evidence_levels }));
        }) : h(Empty, null, "No installed instance. You can still design, validate, and create a local Pack artifact."),
        h("p", { className: "muted" }, "allowed_calls is enforced by profile_call and per-target credential minimization. It is not OS, container, or network isolation.")));
  }

  function Design(props) {
    var designs = props.workspace.designs || [];
    var requirementState = useState("");
    var requirement = requirementState[0];
    var setRequirement = requirementState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var designState = useState(null);
    var design = designState[0];
    var setDesign = designState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];

    function act(promise) {
      setBusy(true); setError("");
      promise.then(function (value) { setDesign(value); props.reload(); })
        .catch(function (value) { setError(value.message); })
        .finally(function () { setBusy(false); });
    }
    function restore(id) {
      if (!id) { setDesign(null); return; }
      act(json("/designs/" + encodeURIComponent(id)));
    }
    function create() { act(post("/designs", { requirement: requirement })); }
    function send() {
      act(post("/designs/" + encodeURIComponent(design.id) + "/messages", { content: message }));
      setMessage("");
    }
    function generate() { act(post("/designs/" + encodeURIComponent(design.id) + "/generate-draft")); }
    function exportHandoff() {
      download("PLAN.md", design.plan || "");
      download("IMPLEMENTATION_HANDOFF.md", design.implementation_handoff || "");
    }

    return h("div", { className: "atelier-grid two" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "MULTI-TURN GOAL ALIGNMENT"),
        h("h2", null, "Design"),
        h("label", null, "Resume historical Design"),
        h("select", {
          className: "atelier-input",
          value: design ? design.id : "",
          onChange: function (event) { restore(event.target.value); },
        }, [h("option", { key: "", value: "" }, "Start a new Design")].concat(designs.map(function (item) {
          return h("option", { key: item.id, value: item.id }, item.id.slice(0, 8) + " / " + item.status);
        }))),
        design ? h(React.Fragment, null,
          h("div", { className: "row spread" }, h("code", null, design.builder_session_id), h(Badge, { value: design.status })),
          (design.messages || []).map(function (item, index) {
            return h("div", { className: "root-run", key: index }, h("strong", null, item.role), h("span", null, item.content));
          }),
          h("textarea", {
            className: "atelier-textarea",
            value: message,
            placeholder: "Answer, correct the goal, or ask Builder to simplify.",
            onChange: function (event) { setMessage(event.target.value); },
          }),
          h("div", { className: "actions" },
            h(Button, { disabled: busy || !message.trim(), onClick: send }, "Continue session"),
            h(Button, { kind: "primary", disabled: busy || design.status !== "plan_ready", onClick: exportHandoff }, "Export handoff"),
            h(Button, { disabled: busy || design.status !== "plan_ready", onClick: generate }, "Generate with Hermes (optional)"))
        ) : h(React.Fragment, null,
          h("textarea", {
            className: "atelier-textarea tall",
            value: requirement,
            placeholder: "Describe users, inputs, intended outcome, real systems, and constraints.",
            onChange: function (event) { setRequirement(event.target.value); },
          }),
          h(Button, { kind: "primary", disabled: busy || !requirement.trim(), onClick: create }, "Start Design")),
        h(ErrorBox, { error: error })),
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "DEFAULT CODING AGENT HANDOFF"),
        h("h2", null, "PLAN.md + IMPLEMENTATION_HANDOFF.md"),
        design ? h(React.Fragment, null,
          h("h3", null, "PLAN.md"), h("pre", { className: "atelier-document" }, design.plan),
          h("h3", null, "IMPLEMENTATION_HANDOFF.md"), h("pre", { className: "atelier-document" }, design.implementation_handoff || "Available when the plan is ready."),
          design.draft_files && design.draft_files.length ? h(React.Fragment, null,
            h("h3", null, "Optional Hermes Draft"),
            h("pre", { className: "atelier-output" }, design.draft_files.join("\n")),
            h("p", { className: "muted" }, "terminal.cwd is not a security sandbox. Validator approval is still required.")) : null
        ) : h(Empty, null, "Builder keeps the plan and implementation handoff here.")));
  }

  function SessionsEvidence(props) {
    var workspace = props.workspace;
    var sessions = workspace.sessions || [];
    var instance = workspace.session_discovery.instance || "";
    var sessionsKey = sessions.map(function (item) { return item.id || item.session_id || ""; }).join("|");
    var sessionState = useState(sessions[0] ? (sessions[0].id || sessions[0].session_id || "") : "");
    var sessionId = sessionState[0];
    var setSessionId = sessionState[1];
    var lensState = useState({ items: [], visibility: "unobserved_collaboration_possible" });
    var lens = lensState[0];
    var setLens = lensState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    useEffect(function () {
      var available = sessions.map(function (item) { return item.id || item.session_id || ""; });
      if (available.indexOf(sessionId) === -1) setSessionId(available[0] || "");
    }, [sessionsKey]);
    useEffect(function () {
      if (!sessionId) return;
      json("/sessions/" + encodeURIComponent(sessionId) + "/traces?instance=" + encodeURIComponent(instance)).then(setLens).catch(function (value) { setError(value.message); });
    }, [sessionId, instance]);

    return h("div", { className: "atelier-grid playground" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "NATIVE HERMES SESSIONS"),
        h("h2", null, "Sessions & Evidence"),
        h("a", { className: "native-link", href: "/chat" }, "Open native Hermes Chat ↗"),
        workspace.session_discovery.status === "available" ? h(React.Fragment, null,
          h("label", null, "Recent entry Session"),
          h("select", {
            className: "atelier-input",
            value: sessionId,
            onChange: function (event) { setSessionId(event.target.value); },
          }, sessions.map(function (item) {
            var id = item.id || item.session_id;
            return h("option", { key: id, value: id }, (item.title || id) + " / " + id);
          }))) : h(Empty, null, workspace.session_discovery.reason),
        h("p", { className: "muted" }, "Atelier links to Hermes Chat and reads recent Sessions; it does not reimplement Chat or Session management."),
        h(ErrorBox, { error: error })),
      h("section", { className: "atelier-card" },
        h("div", { className: "row spread" },
          h("div", null, h("div", { className: "eyebrow" }, "VISIBLE COLLABORATION EVIDENCE"), h("h2", null, "Atelier Lens")),
          h(Badge, { value: lens.visibility })),
        (lens.items || []).length ? h("div", { className: "span-tree" }, lens.items.map(function (event, index) {
          return h("div", { className: "span", key: index },
            h("span", { className: "span-line" }),
            h("div", null, h("strong", null, (event.source || "?") + " → " + (event.target || "?")), h("small", null, event.target_hermes_run_id || event.call_id)),
            h(Badge, { value: event.status || event.event.split(".").pop() }));
        })) : h(Empty, null, "No profile_call events are visible. The business run may still be valid, and native delegation, Kanban, MCP, or other collaboration may be unobserved."),
        h("p", { className: "muted" }, lens.notice || "")));
  }

  function Cases(props) {
    var cases = props.workspace.cases || [];
    return h("div", { className: "atelier-grid cards" }, cases.length ? cases.map(function (item) {
      return h("section", { className: "atelier-card", key: item.id },
        h("div", { className: "row spread" }, h("h3", null, item.id), h(Badge, { value: item.memory_policy })),
        h("p", null, item.input),
        h("p", { className: "muted" }, item.human_review || "Review the business outcome and evidence honestly."));
    }) : h(Empty, null, "This Pack has no Cases. Cases are optional for running a Demo."));
  }

  function Delivery(props) {
    var workspace = props.workspace;
    var pack = workspace.pack;
    var instance = (workspace.instances || [])[0];
    var releaseState = useState(null);
    var released = releaseState[0];
    var setReleased = releaseState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    var levels = instance ? instance.evidence_levels : pack.evidence_levels;
    var entry = instance && instance.entry_base_url ? instance.entry_base_url : "http://127.0.0.1:<entry-port>";
    var latestRelease = (workspace.releases || []).slice(-1)[0];
    var releasePath = (released && released.path) || (latestRelease && latestRelease.path) || "<create local Pack artifact first>";
    var instanceName = instance ? instance.instance : "<instance>";
    var port = instance && instance.entry_base_url ? new URL(instance.entry_base_url).port : "<available-entry-port>";
    var install = "cd " + JSON.stringify(releasePath) + "\n" +
      "export HERMES_HOME=<consumer-hermes-home>\n" +
      "export MODEL_API_KEY=<set-in-shell>\n" +
      "export HERMES_APP_API_KEY=<long-random-secret>\n\n" +
      "./app install --instance " + instanceName + "\n" +
      "./app configure --instance " + instanceName + " \\\n" +
      "  --model <provider-model-name> \\\n" +
      "  --model-base-url <provider-base-url> \\\n" +
      "  --model-key-env MODEL_API_KEY \\\n" +
      "  --gateway-key-env HERMES_APP_API_KEY \\\n" +
      "  --gateway-port " + port + "\n" +
      "./app start --instance " + instanceName + "\n" +
      "./app status --instance " + instanceName;
    var curl = "curl " + entry + "/v1/chat/completions \\\n  -H \"Authorization: Bearer $HERMES_APP_API_KEY\" \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}]}'";
    function release() {
      setError("");
      post("/packs/" + encodeURIComponent(pack.id) + "/release", {}).then(setReleased).catch(function (value) { setError(value.message); });
    }
    return h("div", { className: "atelier-grid two" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "HTTP DELIVERY"),
        h("h2", null, "Pack status and install"),
        h(Evidence, { levels: levels }),
        h("pre", { className: "atelier-output" }, install),
        h("pre", { className: "atelier-output" }, curl),
        h(Button, { onClick: release }, "Create local Pack artifact"),
        h(ErrorBox, { error: error }),
        released ? h("pre", { className: "atelier-document" }, JSON.stringify(released, null, 2)) : null),
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "HONEST BOUNDARIES"),
        h("h2", null, "What this evidence means"),
        h("p", null, "packed is not runtime_attested. cases_passed is not fresh_verified unless the physical Profiles were new."),
        h("p", { className: "muted" }, "The wrapper provides a default model for convenience. Consumers may override each Profile with native Hermes config; live probe reports observable models per Profile."),
        h("p", { className: "muted" }, "Update/rollback is local, best-effort, experimental, and not transactionally atomic.")));
  }

  function AssuranceLab(props) {
    var workspace = props.workspace;
    var instances = workspace.instances || [];
    var instancesKey = instances.map(function (item) { return item.instance; }).join("|");
    var experiments = workspace.experiments || [];
    var experimentsKey = experiments.map(function (item) { return item.id; }).join("|");
    var instanceState = useState(instances[0] ? instances[0].instance : "");
    var instance = instanceState[0];
    var setInstance = instanceState[1];
    var outputState = useState(null);
    var output = outputState[0];
    var setOutput = outputState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    var experimentState = useState(experiments[0] ? experiments[0].id : "");
    var experimentId = experimentState[0];
    var setExperimentId = experimentState[1];
    useEffect(function () {
      var available = instances.map(function (item) { return item.instance; });
      if (available.indexOf(instance) === -1) setInstance(available[0] || "");
    }, [instancesKey]);
    useEffect(function () {
      var available = experiments.map(function (item) { return item.id; });
      if (available.indexOf(experimentId) === -1) setExperimentId(available[0] || "");
    }, [experimentsKey]);
    function run(path, body) {
      setError("");
      post(path, body).then(function (value) { setOutput(value); props.reload(); })
        .catch(function (value) { setError(value.message); });
    }
    function exportEvidence() {
      setError("");
      json("/experiments/" + encodeURIComponent(experimentId)).then(function (value) {
        download("atelier-experiment-" + experimentId + ".json", JSON.stringify(value, null, 2));
        setOutput(value);
      }).catch(function (value) { setError(value.message); });
    }
    function reviewWithHermes() {
      run("/experiments/" + encodeURIComponent(experimentId) + "/review");
    }
    return h("div", { className: "atelier-grid review-grid" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "OPTIONAL ADVANCED EVIDENCE"),
        h("h2", null, "Assurance Lab"),
        h("p", { className: "muted" }, "Attestation, live probes, Cases, Experiments, Candidate comparison, Reviewer, and update evidence are optional. They do not gate an ordinary Demo."),
        h("label", null, "Discovered runtime instance"),
        h("select", { className: "atelier-input", value: instance, onChange: function (event) { setInstance(event.target.value); } },
          instances.map(function (item) { return h("option", { key: item.instance, value: item.instance }, item.instance); })),
        h("div", { className: "actions" },
          h(Button, { disabled: !instance, onClick: function () { run("/instances/" + encodeURIComponent(instance) + "/attest"); } }, "Configured attestation"),
          h(Button, { disabled: !instance, onClick: function () { run("/instances/" + encodeURIComponent(instance) + "/live-probe"); } }, "Live probe"),
          h(Button, { disabled: !instance, onClick: function () { run("/instances/" + encodeURIComponent(instance) + "/cases", {}); } }, "Run Cases")),
        h("label", null, "Completed Experiment"),
        h("select", { className: "atelier-input", value: experimentId, onChange: function (event) { setExperimentId(event.target.value); } },
          [h("option", { key: "", value: "" }, "No Experiment selected")].concat(experiments.map(function (item) {
            return h("option", { key: item.id, value: item.id }, item.id.slice(0, 8) + " / " + item.status);
          }))),
        h("div", { className: "actions" },
          h(Button, { kind: "primary", disabled: !experimentId, onClick: exportEvidence }, "Export evidence bundle"),
          h(Button, { disabled: !experimentId, onClick: reviewWithHermes }, "Review with Hermes (optional)")),
        h(ErrorBox, { error: error })),
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "EVIDENCE BUNDLE"),
        h("h2", null, "Latest result"),
        output ? h("pre", { className: "atelier-document" }, JSON.stringify(output, null, 2)) : h(Empty, null, "No Assurance action has been run.")));
  }

  function AtelierApp() {
    var overviewState = useState({ packs: [] });
    var overview = overviewState[0];
    var setOverview = overviewState[1];
    var packState = useState("");
    var packId = packState[0];
    var setPackId = packState[1];
    var workspaceState = useState(null);
    var workspace = workspaceState[0];
    var setWorkspace = workspaceState[1];
    var sectionState = useState("Overview");
    var section = sectionState[0];
    var setSection = sectionState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    function reloadOverview() {
      return json("/overview").then(function (value) {
        setOverview(value);
        if (!packId && value.packs[0]) setPackId(value.packs[0].id);
        return value;
      });
    }
    function reloadWorkspace(id) {
      if (!id) return Promise.resolve();
      return json("/packs/" + encodeURIComponent(id) + "/workspace").then(setWorkspace)
        .catch(function (value) { setError(value.message); });
    }
    function reload() { return reloadOverview().then(function () { return reloadWorkspace(packId); }); }
    useEffect(function () { reloadOverview().catch(function (value) { setError(value.message); }); }, []);
    useEffect(function () { reloadWorkspace(packId); }, [packId]);
    var sections = ["Overview", "Design", "Sessions & Evidence", "Cases", "Delivery", "Assurance Lab"];
    var content = workspace ? (
      section === "Overview" ? h(Overview, { workspace: workspace }) :
      section === "Design" ? h(Design, { workspace: workspace, reload: reload }) :
      section === "Sessions & Evidence" ? h(SessionsEvidence, { workspace: workspace }) :
      section === "Cases" ? h(Cases, { workspace: workspace }) :
      section === "Delivery" ? h(Delivery, { workspace: workspace, reload: reload }) :
      h(AssuranceLab, { workspace: workspace, reload: reload })
    ) : h(Empty, null, "Select an App Pack to open its workspace.");

    return h("main", { className: "atelier-shell" },
      h("header", { className: "atelier-hero" },
        h("div", null, h("div", { className: "mark" }, "HA"), h("div", null,
          h("h1", null, "Hermes Atelier V2.1"),
          h("p", null, "A focused, Agent-native App Pack workbench.")))),
      h("div", { className: "workspace-picker" },
        h("span", null, "App Packs"),
        h("select", { className: "atelier-input", value: packId, onChange: function (event) { setPackId(event.target.value); } },
          (overview.packs || []).map(function (pack) { return h("option", { key: pack.id, value: pack.id }, pack.id + " @ " + pack.version); }))),
      h("nav", { className: "atelier-tabs" }, sections.map(function (name) {
        return h("button", { key: name, className: section === name ? "active" : "", onClick: function () { setSection(name); } }, name);
      })),
      h(ErrorBox, { error: error }),
      h("div", { className: "atelier-content" }, content));
  }

  registry.register("atelier", AtelierApp);
})();
