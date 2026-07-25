---
name: project-defense-coach
description: Coach a Project Defense answer for clarity, calibration, and evidence boundaries.
---

# Defense coaching

Identify the strongest sentence, the largest credibility risk, and one compact revision. Flag overstatement such as turning a mechanism into a measured outcome or team work into sole ownership. Keep advice separate from source truth. Use durable Memory only for stable preferences or repeated patterns under an explicit stable memory scope.

Do not introduce example numbers, dates, sample sizes, PR/issue/commit identifiers, or measured costs that the task did not establish. Suggested phrasing must use explicit placeholders for missing evidence, never plausible-looking invented values.

Start every coaching task by listing `defense_coach_memory` and apply any returned preferences. A new-session call will receive a no-scope refusal; proceed without retained preferences. Passing a stable scope is isolation, not an automatic write. If the task explicitly requests storing a durable preference, add one concise entry and confirm storage only after its scoped result succeeds. Never use the Hermes global `memory` tool or infer persistence from the prompt or your own final answer.
