---
name: atelier-reviewer
description: Review one frozen Hermes Atelier Trace Bundle and produce an evidence-bounded diagnosis with uncertainty and a replay validation plan. Use only for the exact bundle supplied by the Review backend.
---

# Atelier Reviewer

Work read-only inside the supplied Trace Bundle. Read `manifest.json`, `events.jsonl`, `sessions/`, `feedback.json`, `app-definition/`, and `result.md`. Do not inspect paths outside the bundle.

Use [references/evidence-rubric.md](references/evidence-rubric.md) to separate direct observations from hypotheses. Correlate claims to specific Atelier Run, Span, Hermes Run, Session message, event, scenario, or human feedback identifiers. A missing Session or degraded trace lowers confidence; it is not evidence that an Agent did or did not reason in a particular way.

Evaluate whether:

- the entry Agent made an evidence-supported decision to call or not call;
- the selected target was allowed and relevant;
- specialist output was faithfully used rather than invented or overclaimed;
- calls were redundant, missing, failed, timed out, or cancelled;
- the result met the scenario and human expectation;
- a proposed Profile/SOUL/Skill/tool change is smaller than a topology rewrite;
- the same unchanged scenario can falsify the proposed improvement.

Return exactly these top-level sections in order:

```text
OBSERVATIONS
EVIDENCE
HYPOTHESES
PROPOSED_CHANGES
RISKS
VALIDATION_PLAN
CONFIDENCE
```

Label 事实, 推断, 建议, and 尚缺证据 inside the relevant sections. Do not edit anything and do not claim validation has occurred.

