# Architecture

```text
Hermes Dashboard
└── atelier Plugin
    ├── Dashboard Tab + local FastAPI routes
    ├── atelier_call tool
    ├── lightweight CLI
    └── SQLite services

<repo>/.hermes-runtime
├── profiles/atelier-builder
├── profiles/atelier-reviewer
└── profiles/<app-id>--<role>

apps/<app-id>          versioned definitions and Distributions
.atelier/atelier.db    single Atelier state source
```

Each Profile runs its own Hermes Gateway/API Server on a distinct `127.0.0.1` port. A Playground request creates one Atelier Run, then starts the entry Profile with Session `at_<run-id>_root`. When that Agent chooses `atelier_call`, the plugin obtains its Hermes Profile, `session_id`, and `task_id`, validates `allowed_calls`, creates a Span, starts the target Run with Session `at_<run-id>_<span-id>`, consumes SSE, and returns the real target result.

Atelier does not proxy reasoning or prescribe a topology. A child Agent may call another allowed Agent, producing a nested Span. The database records relationships and normalized events; Hermes owns every transcript, Memory, Skill, tool loop, and Run.

Builder writes only `apps/.drafts/<build-id>/`. Approval promotes exactly one validated application, installs native Distributions, writes runtime `.env` files, starts Gateways, and registers the app. Reviewer receives only a frozen Trace Bundle. Proposal apply validates every patch path, performs `git apply --check`, records approval, updates affected native Profiles, and can revert.

The Dashboard is not a resident Atelier service. Stopping it does not stop independent business Profile Gateways.

## Source/runtime split

Checked-in Profile directories are Distribution source. Runtime Profiles live below the absolute project-local `HERMES_HOME`. Hermes native update owns replacement and preserves its user-owned `.env`, Memory, Sessions, credentials, logs, workspaces, and local state. Atelier materializes model/Base URL and absolute `terminal.cwd` only in runtime configuration; secrets remain in mode-0600 `.env` files.
