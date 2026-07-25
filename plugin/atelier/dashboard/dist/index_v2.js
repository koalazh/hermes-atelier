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
    return h("button", { className: "atelier-button " + (props.kind || ""), disabled: props.disabled, onClick: props.onClick }, props.children);
  }
  function Badge(props) { return h("span", { className: "atelier-badge " + (props.value || "") }, props.value || "—"); }
  function ErrorBox(props) { return props.error ? h("div", { className: "atelier-error" }, String(props.error)) : null; }
  function Empty(props) { return h("div", { className: "atelier-empty" }, props.children); }

  function DesignView(props) {
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
    function create() { act(post("/designs", { requirement: requirement })); }
    function send() {
      act(post("/designs/" + design.id + "/messages", { content: message }));
      setMessage("");
    }
    function generate() { act(post("/designs/" + design.id + "/generate-draft")); }
    return h("div", { className: "atelier-grid two" },
      h("section", { className: "atelier-card" },
        h("div", { className: "eyebrow" }, "CONVERSATION → PLAN"), h("h2", null, "Design with Builder"),
        design ? h(React.Fragment, null,
          h("div", { className: "row spread" }, h("code", null, design.builder_session_id), h(Badge, { value: design.status })),
          (design.messages || []).map(function (item, index) { return h("div", { className: "root-run", key: index }, h("strong", null, item.role), h("span", null, item.content)); }),
          h("textarea", { className: "atelier-textarea", value: message, placeholder: "Answer, correct the goal, or ask Builder to simplify.", onChange: function (event) { setMessage(event.target.value); } }),
          h("div", { className: "actions" }, h(Button, { disabled: busy || !message.trim(), onClick: send }, "Continue session"), h(Button, { kind: "primary", disabled: busy || design.status !== "plan_ready", onClick: generate }, "Generate Draft"))
        ) : h(React.Fragment, null,
          h("textarea", { className: "atelier-textarea tall", value: requirement, placeholder: "Describe users, inputs, intended outcome, real systems, and constraints.", onChange: function (event) { setRequirement(event.target.value); } }),
          h(Button, { kind: "primary", disabled: busy || !requirement.trim(), onClick: create }, "Start Design")
        ), h(ErrorBox, { error: error })),
      h("section", { className: "atelier-card" }, h("div", { className: "eyebrow" }, "DECISION ANCHOR"), h("h2", null, "PLAN.md"),
        design ? h(React.Fragment, null, h("pre", { className: "atelier-document" }, design.plan), design.draft_files && design.draft_files.length ? h(React.Fragment, null, h("h3", null, "Inspectable Draft"), h("pre", { className: "atelier-output" }, design.draft_files.join("\n")), h("p", { className: "muted" }, "Adopt through a Git branch/worktree; Atelier does not apply patches to the current tree.")) : null) : h(Empty, null, "A multi-turn Builder Session will maintain the plan here."))
    );
  }

  function RunView(props) {
    var sessionState = useState("");
    var sessionId = sessionState[0];
    var setSessionId = sessionState[1];
    var traceState = useState([]);
    var traces = traceState[0];
    var setTraces = traceState[1];
    var pack = props.packs[0];
    function refresh() { if (sessionId) json("/sessions/" + sessionId + "/traces").then(function (value) { setTraces(value.items || []); }); }
    return h("div", { className: "atelier-grid playground" },
      h("section", { className: "atelier-card" }, h("div", { className: "eyebrow" }, "RUN THROUGH HERMES"), h("h2", null, "Native multi-turn Session"),
        pack ? h(React.Fragment, null, h("dl", { className: "meta" }, h("dt", null, "Pack"), h("dd", null, pack.id), h("dt", null, "Entry"), h("dd", null, pack.entry), h("dt", null, "State"), h("dd", null, pack.state_policy)), h("p", { className: "muted" }, "Continue the conversation in Hermes Chat or call the entry Profile's OpenAI-compatible HTTP API. Atelier does not wrap Chat, Session, or Run lifecycle."), h("a", { className: "native-link", href: "/chat" }, "Open native Hermes Chat ↗")) : h(Empty, null, "No valid App Pack."),
        h("label", null, "Current Hermes Session ID"), h("input", { className: "atelier-input", value: sessionId, onChange: function (event) { setSessionId(event.target.value); } }), h(Button, { disabled: !sessionId, onClick: refresh }, "Load real calls")),
      h("section", { className: "atelier-card" }, h("div", { className: "eyebrow" }, "CURRENT SESSION TRACE"), h("h2", null, "profile_call evidence"), traces.length ? h("div", { className: "span-tree" }, traces.map(function (event, index) { return h("div", { className: "span", key: index }, h("span", { className: "span-line" }), h("div", null, h("strong", null, event.source + " → " + event.target), h("small", null, event.target_hermes_run_id || event.call_id)), h(Badge, { value: event.status || event.event.split(".").pop() })); })) : h(Empty, null, "No indexed cross-Profile calls. Business execution remains valid if this view is empty."))
    );
  }

  function EvaluateView(props) {
    var packState = useState("");
    var packId = packState[0];
    var setPackId = packState[1];
    var caseState = useState("");
    var caseId = caseState[0];
    var setCaseId = caseState[1];
    var casesState = useState([]);
    var cases = casesState[0];
    var setCases = casesState[1];
    var endpointState = useState("");
    var endpoint = endpointState[0];
    var setEndpoint = endpointState[1];
    var experimentState = useState(null);
    var experiment = experimentState[0];
    var setExperiment = experimentState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    useEffect(function () { if (!packId && props.packs[0]) setPackId(props.packs[0].id); }, [props.packs.length]);
    useEffect(function () { if (packId) json("/packs/" + packId + "/cases").then(function (value) { setCases(value.items || []); setCaseId(value.items && value.items[0] ? value.items[0].id : ""); }); }, [packId]);
    function run() {
      setError("");
      post("/experiments", { pack_id: packId, case_id: caseId, entry_base_url: endpoint, api_key_env: "HERMES_APP_API_KEY", model_fingerprint: { source: "operator-declared" }, trial_count: 1 })
        .then(function (value) { setExperiment(value); props.reload(); }).catch(function (value) { setError(value.message); });
    }
    return h("div", { className: "atelier-grid review-grid" },
      h("section", { className: "atelier-card" }, h("div", { className: "eyebrow" }, "CASE → EXPERIMENT"), h("h2", null, "Run frozen evidence"),
        h("label", null, "App Pack"), h("select", { className: "atelier-input", value: packId, onChange: function (event) { setPackId(event.target.value); } }, props.packs.map(function (pack) { return h("option", { key: pack.id, value: pack.id }, pack.id + " @ " + pack.revision.slice(0, 8)); })),
        h("label", null, "Case"), h("select", { className: "atelier-input", value: caseId, onChange: function (event) { setCaseId(event.target.value); } }, cases.map(function (item) { return h("option", { key: item.id, value: item.id }, item.id + " / " + item.memory_policy); })),
        h("label", null, "Entry Hermes base URL"), h("input", { className: "atelier-input", value: endpoint, onChange: function (event) { setEndpoint(event.target.value); }, placeholder: "http://127.0.0.1:8080" }), h("p", { className: "muted" }, "The API key is read from HERMES_APP_API_KEY; secrets are never sent in this form."), h(Button, { kind: "primary", disabled: !packId || !caseId || !endpoint, onClick: run }, "Run Experiment"), h(ErrorBox, { error: error })),
      h("section", { className: "atelier-card" }, h("div", { className: "row spread" }, h("div", null, h("div", { className: "eyebrow" }, "DEFINITION + MODEL + MEMORY"), h("h2", null, "Experiment evidence")), experiment ? h(Badge, { value: experiment.status }) : null), experiment ? h("pre", { className: "atelier-document" }, JSON.stringify(experiment, null, 2)) : h(Empty, null, "Trials, real Runs, calls, assertions, and human feedback appear here."))
    );
  }

  function ReleaseView(props) {
    var releasedState = useState(null);
    var released = releasedState[0];
    var setReleased = releasedState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    function release(pack) { setError(""); post("/packs/" + pack.id + "/release", {}).then(setReleased).catch(function (value) { setError(value.message); }); }
    return h("div", null, h("div", { className: "section-heading" }, h("div", null, h("div", { className: "eyebrow" }, "DELIVER THROUGH APP PACKS"), h("h2", null, "Validated releases"))), h(ErrorBox, { error: error }), h("div", { className: "atelier-grid cards" }, props.packs.map(function (pack) { return h("section", { className: "atelier-card", key: pack.id }, h("div", { className: "row spread" }, h("h3", null, pack.id), h("code", null, pack.version)), h("dl", { className: "meta" }, h("dt", null, "Revision"), h("dd", null, pack.revision), h("dt", null, "Public"), h("dd", null, pack.entry), h("dt", null, "Cases"), h("dd", null, String(pack.cases.length))), h(Button, { onClick: function () { release(pack); } }, "Create release")); })), released ? h("pre", { className: "atelier-document" }, JSON.stringify(released, null, 2)) : null);
  }

  function AtelierApp() {
    var tabState = useState("Design");
    var tab = tabState[0];
    var setTab = tabState[1];
    var overviewState = useState({ packs: [], designs: [], experiments: [] });
    var overview = overviewState[0];
    var setOverview = overviewState[1];
    function reload() { return json("/overview").then(setOverview); }
    useEffect(function () { reload().catch(function () {}); }, []);
    var tabs = ["Design", "Run & Observe", "Evaluate", "Release"];
    var content = tab === "Design" ? h(DesignView, { reload: reload }) : tab === "Run & Observe" ? h(RunView, { packs: overview.packs }) : tab === "Evaluate" ? h(EvaluateView, { packs: overview.packs, reload: reload }) : h(ReleaseView, { packs: overview.packs });
    return h("main", { className: "atelier-shell" },
      h("header", { className: "atelier-hero" }, h("div", null, h("div", { className: "mark" }, "HA"), h("div", null, h("h1", null, "Hermes Atelier V2"), h("p", null, "Design through conversation. Run through Hermes. Observe through Atelier. Evaluate through cases.")))),
      h("nav", { className: "atelier-tabs" }, tabs.map(function (name) { return h("button", { key: name, className: tab === name ? "active" : "", onClick: function () { setTab(name); } }, name); })),
      h("div", { className: "atelier-content" }, content));
  }

  registry.register("atelier", AtelierApp);
})();
