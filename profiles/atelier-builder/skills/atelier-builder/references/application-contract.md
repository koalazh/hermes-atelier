# Hermes App Pack V2 contract

The candidate root contains `app.yaml`, Profile Distributions, Cases, and optional contracts.

`app.yaml` uses `schema_version: 2` and contains stable facts only:

- kebab-case Pack `id` and version;
- one logical public `entry` Agent;
- logical `agents` mapped to relative Profile Distribution paths and exposure;
- `allowed_calls` as a permission boundary, never a routing rule;
- required collaboration primitives;
- native OpenAI-compatible public endpoints;
- `stateless`, `session_only`, or `caller_scoped` state policy;
- relative Case and contract paths.

Never add steps, workflow, if/else, route predicates, parallel branches, fan-out, aggregation,
judging, prompt chains, or business retries. Cases describe input, initial state, explicit Memory
policy, a small set of outcome assertions, and a human review prompt. They do not prescribe Agent
steps.

Every logical Agent is a complete local Hermes Profile Distribution. Business SOUL and Skills use
logical IDs, never installed physical Profile names. If `profile_call` is selected, callers use
logical targets and the release process embeds the independent Plugin. Do not depend on Atelier,
`.atelier`, Atelier Sessions, an Endpoint registry, a PID manager, or `atelier_call`.

Do not place API keys, `.env`, Memory, Sessions, traces, PID files, logs, `local/`, or runtime
configuration in the candidate. Missing integrations remain explicit; deterministic mock tools
must identify their output as simulated.
