---
name: atelier-builder
description: Align a business intent and create a minimal, complete Hermes Profile application in the exact Atelier draft directory. Use when the Atelier Build backend supplies a BUILD.md contract and asks for an application proposal.
---

# Atelier Builder

Read `BUILD.md` and the supplied original request. Inspect the current draft, repository conventions, and available Hermes capabilities before choosing boundaries.

Keep `BUILD.md` current under these headings:

- Original Request
- Aligned Goal
- Users and Inputs
- Expected Output
- Profile Boundaries
- Tools and Data
- Memory and Skill Ownership
- HTTP Collaboration
- Observability Needs
- Acceptance Scenarios
- Missing Real Integrations
- Risks
- Status

Ask focused questions in your response only when a missing fact materially changes the goal, safety boundary, Profile split, required real integration, or acceptance result. Otherwise make a reversible, disclosed assumption and proceed.

Before splitting a Profile, record at least one concrete justification from the boundary rubric in [references/profile-boundaries.md](references/profile-boundaries.md). Do not use familiar names such as Router, Researcher, or Reviewer as a substitute for evidence.

Create exactly one candidate application below the supplied draft directory. Follow [references/application-contract.md](references/application-contract.md). Every Profile must be a valid local Hermes Distribution with its own SOUL, config, and only the Skills it owns. Profile names are `<app-id>--<role>` and all cross-Profile calls use `atelier_call`.

Design acceptance scenarios that test meaningful variation, including when the entry Profile should not call a specialist, may call one, and may call more than one when the application naturally permits it. Keep business-specific tools, examples, prompts, routes, and evaluation criteria in the application assets.

Before stopping:

1. validate every `distribution.yaml`, `config.yaml`, Skill, and `app.yaml`;
2. ensure `app.yaml` has no workflow or routing language;
3. list missing real integrations and credentials without fabricating them;
4. set `BUILD.md` Status to `AWAITING_APPROVAL`;
5. summarize the proposed boundaries and evidence, without claiming approval, installation, health, or smoke success.

The backend performs promotion, Profile installation, runtime secret creation, Gateway startup, smoke execution, and registration only after explicit human approval.

