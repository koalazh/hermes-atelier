# Application contract

The candidate root contains `app.yaml`, `profiles/`, and `scenarios/`.

`app.yaml` contains only:

- `schema_version: 1`;
- kebab-case application `id` and `display_name`;
- one declared `entry_profile`;
- a list of namespaced Profile Distribution source paths;
- explicit `allowed_calls` between declared Profiles;
- `scenarios_dir` and optional descriptive text.

Never add `steps`, `workflow`, `if`, `else`, `route_when`, `parallel`, `fan_out`, `aggregate`, `judge`, or business retry policy.

Each Profile source must contain `distribution.yaml`, `SOUL.md`, `config.yaml`, and the minimal owned Skills/tools. Use `${ATELIER_PROJECT_ROOT}` for a repository path in versioned source; the installed runtime receives the absolute value. Never place Endpoint, port, PID, API key, Memory, Session, logs, or runtime state in the candidate.

The entry Profile decides whether a call is useful. `atelier_call` accepts a target, complete task, optional stable Memory scope, and timeout. Do not ask Atelier to choose, route, sequence, retry, aggregate, judge, or summarize specialists.

