# Security

Atelier V1 is a trusted local-development plugin. Dashboard and every Profile API Server bind only to `127.0.0.1`; startup rejects `0.0.0.0` and documentation provides no public deployment recipe. `HERMES_HOME` isolates Hermes state from `~/.hermes`, but it is not an operating-system sandbox.

API keys exist only in ignored Profile `.env` files with mode 0600. The database stores host/port references, never Profile API secrets. Browser responses expose endpoints and missing variable names, not values. Authorization headers, key-shaped strings, and common secret assignments are redacted from events, summaries, feedback bundles, errors, and Builder input persistence.

All Profile names, sources, scenario paths, draft paths, Trace Bundle paths, and patch paths are validated and resolved beneath their declared roots. Builds reject symlinks and runtime secret files. Proposals can change only `apps/<current-app-id>/`, require dry-run and explicit approval, and cannot touch Atelier, system Profiles, runtime state, database, `.env`, another app, or Hermes core.

The Project Defense Source Profile demonstrates a narrower capability boundary: terminal, file, project, and code-execution toolsets are disabled, and a dedicated read-only plugin resolves every requested path beneath one declared workspace. Profiles that need stronger process or network isolation should use a Hermes-supported Docker backend.

Trace-store failure is visible. Atelier never substitutes another expert, invents a successful output, or implements a business retry. Child timeout requests native Hermes stop and reports `child_timeout`, not “stopped.”
