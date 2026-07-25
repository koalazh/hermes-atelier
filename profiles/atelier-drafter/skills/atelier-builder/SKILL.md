---
name: atelier-builder
description: Generate exactly one Hermes App Pack V2 Draft from an approved PLAN.md in the explicitly supplied writable directory.
---

# Atelier Builder Draft mode

Read the approved plan supplied by the request. Create exactly one V2 App Pack beneath the exact
Draft directory. Use logical Agent IDs and valid Hermes Profile Distributions. A single business
Profile is the default unless the plan records a concrete boundary.

The Pack manifest uses `schema_version: 2`, one public logical entry, internal Agents, permission-
only `allowed_calls`, native OpenAI-compatible endpoints, explicit state policy, Cases, and
contracts. It contains no workflow, routing, retry, aggregation, judging, physical installed
Profile name, secret, Memory, Session, trace, PID, Endpoint registry, or Atelier runtime
dependency. Cases specify inputs, Memory policy, outcome assertions, and human review guidance,
not Agent steps.

Use this exact manifest shape, adapting values but not field names:

```yaml
schema_version: 2
id: support-helper
version: 0.1.0
entry: entry
agents:
  entry:
    distribution: profiles/entry
    exposure: public
allowed_calls: {}
collaboration: []
public_api:
  protocol: openai
  endpoints: [/v1/responses, /v1/chat/completions]
state_policy: session_only
cases: [cases/smoke.yaml]
contracts: []
```

Each `agents.*.distribution` directory is a Hermes Profile Distribution containing at least
`distribution.yaml`, `SOUL.md`, and `config.yaml`. A minimal Case is:

```yaml
id: smoke
input: "A realistic user input"
memory_policy: new_session
assertions: {}
human_review: "What a reviewer should inspect in the outcome."
```

The root file must be named `app.yaml`, never `pack.yaml`. Do not invent nested `agents/*.yaml`,
`profile.yaml`, or a different Pack schema.

If cross-Profile HTTP collaboration is justified, use the independent logical-ID `profile_call`
primitive. Never use `atelier_call`.

Validate the generated YAML and Distribution structure before reporting. State which checks were
actually run and keep missing real integrations explicit.
