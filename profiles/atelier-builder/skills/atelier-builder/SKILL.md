---
name: atelier-builder
description: Align a Hermes App Pack goal over multiple planning turns, or generate a V2 Draft only when the explicit Draft-stage prompt supplies a writable directory.
---

# Atelier Builder V2

During planning, investigate and return a complete current `PLAN.md` in the response. Do not
write application files. Ask focused questions only when an answer materially changes the goal,
safety boundary, Profile split, real integration, public contract, state policy, or acceptance
evidence. Otherwise make a reversible, disclosed assumption.

The plan is a decision anchor, not a workflow. It should cover the aligned outcome, users and
inputs, expected result, justified Profile boundaries, tools and data, Memory/Skill/Session
ownership, collaboration primitive, public HTTP contract, Cases, missing real integrations, and
risks. Sections may vary when the application does not need one.

Start every planning response with exactly `DESIGN_STATUS: NEEDS_INPUT` while material questions
remain, or `DESIGN_STATUS: PLAN_READY` when the remainder of the response is the complete current
plan. Never mark a list of unanswered questions as ready.

Use only the current Session. Never search prior Sessions or reuse another Design's requirement,
plan, filesystem path, assumptions, or generated files.

Before splitting a Profile, record a concrete justification from
[references/profile-boundaries.md](references/profile-boundaries.md). A single Profile is the
default. Do not select familiar role names as a substitute for a real permission, knowledge,
workspace, failure, model, evolution, reuse, or context boundary.

Only an explicit Draft-stage prompt supplies a writable directory. In that stage, read the
approved plan from the prompt, create exactly one App Pack beneath the supplied directory, and
follow [references/application-contract.md](references/application-contract.md). Generating a
Draft does not adopt, install, start, commit, or approve it.

Before stopping in Draft stage:

1. validate every Distribution, Profile config, Skill, Plugin, Case, contract, and `app.yaml`;
2. keep workflow and routing behavior out of `app.yaml` and Cases;
3. list missing real integrations and credentials without fabricating them;
4. report exactly what was generated and what was not run.
