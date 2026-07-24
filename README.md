# Hermes Atelier

Hermes Atelier is a project-local development workbench for building complete Hermes Profiles, running their real collaboration, reviewing trace evidence, and applying only human-approved candidate changes.

```text
Build → Run → Observe → Review → Propose → Approve → Replay
```

It is one Hermes Plugin, not a Runtime, workflow engine, AgentHub, production trace platform, or replacement Dashboard.

## Quick start

Requires Hermes Agent 0.19.0 or newer, Python 3.11+, and `uv`.

```bash
uv sync --all-extras
export HERMES_HOME="$(pwd)/.hermes-runtime"
uv run python scripts/bootstrap.py \
  --model YOUR_MODEL \
  --base-url https://your-openai-compatible-endpoint/v1 \
  --api-key YOUR_KEY
uv run python scripts/start.py --dashboard
```

Open `http://127.0.0.1:9119/atelier`. The startup script rejects public Dashboard binds. Runtime state lives only in `.hermes-runtime/` and `.atelier/`; both are ignored.

Useful commands:

```bash
uv run python scripts/status.py
uv run python scripts/smoke_test.py mini-voc --scenario clarify.yaml
uv run python scripts/smoke_test.py project-defense --scenario evidence-gap.yaml
uv run python scripts/stop.py
uv run pytest
```

See [Project](docs/PROJECT.md), [Architecture](docs/ARCHITECTURE.md), [Builder](docs/BUILDER.md), [Trace model](docs/TRACE_MODEL.md), [Security](docs/SECURITY.md), and [Validation](docs/VALIDATION.md).
