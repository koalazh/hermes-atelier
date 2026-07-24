# Hermes Atelier V1 Refactor Plan

## 1. Audit baseline

Audit date: 2026-07-24

Repository: `/Users/koala/work/product/hermes-atelier`

Hermes runtime inspected:

- Version: Hermes Agent `0.19.0` (`2026.7.20`)
- Upstream commit: `9eb7b1a6b1ffdd4ad1a85aee3f38edceee2b927f`
- Install directory: `/Users/koala/.hermes/hermes-agent`
- Install method: Git checkout
- Local status: one upstream commit behind
- Existing changes in the Hermes checkout: modified `package-lock.json` and untracked `.install_method`

The Hermes checkout is read-only evidence for this project. Atelier must not update it, patch it, or absorb its existing uncommitted files.

The Atelier repository is an initialized, clean Git repository with no commits and no tracked or untracked project files before this audit. There is therefore no legacy Atelier implementation to preserve, migrate, or delete. The correct refactor is a clean V1 implementation against the current Hermes public surfaces, not a compatibility layer around nonexistent code.

## 2. Existing-asset classification

| Classification | Current assets | Decision |
| --- | --- | --- |
| `KEEP` | None | The repository was empty. |
| `CONVERT_TO_ATELIER_PLUGIN` | None | Build one `atelier` plugin from the V1 contract. Do not create parallel resident services. |
| `CONVERT_TO_BUILDER_ASSET` | None | Create one complete `atelier-builder` Profile Distribution and a thin Builder Skill. |
| `CONVERT_TO_REVIEWER_ASSET` | None | Create one complete, independent `atelier-reviewer` Profile Distribution and read-only Reviewer Skill. |
| `KEEP_AS_EXAMPLE` | None | Create Mini VOC and Project Defense as new application definitions; keep all business behavior inside their Profiles, SOULs, Skills, and tools. |
| `DELETE` | None | No repository content existed to remove. Runtime directories will be ignored rather than committed. |
| `VERIFY_AGAINST_CURRENT_HERMES` | All integration surfaces below | Treat the installed Hermes 0.19.0 source and real smoke tests as the compatibility oracle. |

## 3. Current Hermes capability audit

### 3.1 Confirmed from the installed 0.19.0 source

| Capability | Evidence in installed Hermes | Atelier decision |
| --- | --- | --- |
| Custom root and named Profile isolation | `hermes_constants.get_default_hermes_root()` treats a custom `HERMES_HOME` as the root and stores named Profiles in `<root>/profiles/<name>`; `-p` resolves before runtime imports. | Every Atelier subprocess receives the absolute repository `.hermes-runtime` as `HERMES_HOME` and an explicit `-p <profile>`. Never use sticky Profile selection. |
| Profile Distribution install/update | `hermes_cli/profile_distribution.py` supports local directories with `distribution.yaml`. Distribution-owned files are replaced; `.env`, Memory, Session databases, credentials, logs, workspaces, and `local/` are protected. `config.yaml` is preserved unless `--force-config` is explicit. | Keep versioned Distribution source in the repository and use `hermes profile install ... --yes` / `hermes profile update ... --yes`. Do not copy Hermes user state ourselves. |
| Plugin tool registration | `PluginContext.register_tool()` registers one schema/handler with the native registry. Registry dispatch forwards runtime keyword arguments to the handler. | Register only `atelier_call`; no remote-agent registry or workflow tool family. |
| Tool execution context | `model_tools.py` dispatches plugin tools with `task_id` and `session_id`. `PluginContext.profile_name` resolves the active caller Profile without relying on CLI state. | Capture caller Profile at plugin registration and require non-empty `task_id` and `session_id`. Fail closed on incompatible Hermes rather than inferring identity. |
| Project/user plugin discovery | Hermes scans root/profile `plugins/` and project `./.hermes/plugins/`; plugins are opt-in through `plugins.enabled`. | `bootstrap.py` links the trusted repository plugin into the root and every installed Profile and enables `atelier`. Source remains `plugin/atelier`; runtime links are ignored. |
| Dashboard plugin backend | A Dashboard manifest can name `plugin_api.py`; Hermes mounts its `APIRouter` below `/api/plugins/<manifest-name>/`. | Expose all Atelier local backend routes through the one plugin API module. |
| Dashboard plugin frontend | Runtime bundles register through `window.__HERMES_PLUGINS__`; `window.__HERMES_PLUGIN_SDK__` exposes host React, hooks, components, authenticated `fetchJSON`, `authedFetch`, and URL/auth helpers. | Ship an IIFE bundle with no bundled React and call only the SDK client. |
| API Server Sessions | API Server exposes create/get/messages/fork/chat routes under `/api/sessions`. | Hermes remains transcript owner. Trace export fetches only referenced Session messages. |
| API Server Runs | `POST /v1/runs` accepts `input`, optional `instructions`, `session_id`, conversation history, and the `X-Hermes-Session-Key` header. It returns `202` plus `run_id`. | Root and child calls use explicit Atelier transcript Session IDs. Stable Memory scope is sent separately only when provided. |
| Run observation/control | `GET /v1/runs/{id}/events` streams structured SSE until terminal status. `GET` polls current status; `POST .../stop` returns `stopping`; `POST .../approval` resolves tool approval. Terminal status records have a finite TTL. | Consume SSE during execution and persist normalized events immediately. A stop request is not reported as stopped until a terminal event/status proves it. |
| Independent API Servers | Hermes Gateway config supports a per-Profile API Server with required key and loopback bind guard. | V1 allocates one local port and secret per Profile, writes only its ignored runtime `.env`, and starts/stops each Gateway independently. |
| Dashboard/Profile management | Hermes Dashboard already owns Profile switcher, Config, credentials, Skills, MCP, Sessions, Chat, logs, and Gateway management. | Atelier UI links to native Profile management and does not recreate those editors. |

### 3.2 Required capability tests before compatibility is claimed

Source inspection establishes the intended interface but does not prove the installed runtime wiring. The implementation must add and run tests that directly establish:

1. a registered `atelier_call` handler receives the exact `task_id` and `session_id` values dispatched by Hermes 0.19.0 and resolves its active Profile;
2. a custom absolute `HERMES_HOME` installs a local Distribution into `.hermes-runtime/profiles/<name>` without touching `~/.hermes`;
3. updating a Distribution preserves a marker in `.env` and Hermes-owned Session state;
4. one independently started Gateway per Profile binds only to its assigned `127.0.0.1` port and passes `/health`/capability checks;
5. Sessions, Runs, SSE terminal events, stop, and API authentication match the inspected shapes;
6. the Dashboard discovers the root `atelier` manifest, mounts `plugin_api.py`, and loads the SDK-only bundle;
7. a root Agent call and a child `atelier_call` produce real, linked Hermes run IDs and Session IDs in the Atelier database.

If test 1 fails, `atelier_call` must return a structured `incompatible_hermes` error and documentation must state a higher minimum version. No alternate runtime or natural-language Run ID is allowed.

## 4. Duplication analysis

The following would duplicate Hermes and will not be built:

- a Profile registry or custom Profile directory format;
- a Session or transcript store;
- an Agent execution loop or model router;
- Memory, Skill, MCP, plugin, credential, or Gateway management pages;
- a general remote Agent mesh;
- a workflow graph, step runner, business retry policy, router, fan-out, aggregate, or judge primitive;
- a second Dashboard server or resident Atelier daemon;
- JSONL mirroring of every database event.

Atelier adds only the missing development-workbench boundary:

- versioned application membership and call allowlists;
- runtime Endpoint references without browser-visible secrets;
- a trustworthy, observable cross-Profile call seam;
- an Atelier Run that correlates Profile-local Hermes Sessions and Runs;
- build/review/proposal approval state and path-restricted patch application;
- a thin Dashboard tab over those local operations.

## 5. Target implementation map

The repository will converge on four core asset groups:

1. `plugin/atelier/`: one trusted Hermes plugin containing `atelier_call`, the plugin CLI, SQLite-backed services, Dashboard routes, and an SDK-only frontend bundle;
2. `profiles/atelier-builder/` and `profiles/atelier-reviewer/`: complete Profile Distribution sources;
3. `apps/<app-id>/`: immutable-by-default application definitions, Profile Distribution sources, Skills, and scenarios;
4. ignored `.hermes-runtime/` and `.atelier/`: Hermes runtime state and the single Atelier SQLite database/proposal/export state.

The implementation may split Python modules further where a tested boundary requires it, but it must not introduce another process or another authoritative state store.

## 6. Compatibility decisions

- Minimum supported Hermes version starts at `>=0.19.0`, because the inspected tool context, Runs API, Dashboard SDK, and Distribution behavior are all present there. Capability checks, not the version string alone, decide runtime compatibility.
- The repository stays compatible with Hermes's actual manifest name `distribution.yaml`; no Atelier-specific Distribution wrapper is introduced.
- The checked-in `plugin/atelier` is source. Runtime installation uses local symbolic links when supported and a safe copy fallback, so editing one repository remains authoritative without committing runtime copies.
- Root and child transcript IDs follow `at_<run-id>_root` and `at_<run-id>_<span-id>`. The parser accepts only Atelier-created identifiers recorded in SQLite; it never trusts arbitrary natural-language identity claims.
- The caller Profile comes from the Hermes plugin context, not a tool argument. `target` is allowlisted against the caller's registered application revision.
- API keys remain only in ignored Profile `.env` files and server-side endpoint records. Endpoint API responses expose health and host/port metadata but never secret values or `.env` contents.
- SQLite write failure marks `trace_degraded`. If the call authorization or parent/child link cannot be established durably before dispatch, the child call fails rather than returning an untraceable success. If event persistence degrades after dispatch, the real downstream result/error is returned with explicit degraded-trace metadata.
- HTTP retries are limited to idempotent connection establishment/reads. Atelier never selects a fallback expert and never implements business retry policy.

## 7. Build order and verification gates

The build order follows complete capabilities, not file-count milestones:

1. plugin skeleton, schema validation, SQLite migrations, app registry;
2. local Hermes root bootstrap and Profile lifecycle;
3. `atelier_call`, Hermes HTTP client, Run/Span/Event persistence, redaction and errors;
4. Dashboard Build/Apps routes and UI;
5. Playground, SSE and trace tree;
6. Builder draft contract and explicit approval installation;
7. Reviewer, frozen Trace Bundle, proposal validation/apply/reject and replay;
8. Mini VOC then Project Defense using the same core;
9. security, degradation, documentation, full regression, real Hermes smoke, visual inspection, and adversarial completion review.

Every capability is committed only after its focused tests pass. Push, publication, public binding, and Hermes-core changes remain outside this repository's authority.

## 8. Audit conclusion

There is no old Atelier code to refactor. Hermes 0.19.0 already supplies the runtime, Profile isolation and distribution, Sessions, Memory, Skills, Plugins, independent Gateways/API Servers, Runs/SSE, and Dashboard extension host required by the design. Hermes Atelier V1 should therefore be a deliberately small local plugin plus versioned Profile assets and one correlation database. Any implementation that adds a workflow engine or reproduces Hermes management surfaces would contradict both the product contract and the current runtime evidence.
