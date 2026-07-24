# Validation evidence

Validated on 2026-07-24 against Hermes Agent 0.19.0 (`2026.7.20`, commit `9eb7b1a6b1ffdd4ad1a85aee3f38edceee2b927f`). The upstream checkout was inspected read-only and retained its pre-existing changes.

## Current evidence

- 9 native Profile Distributions parsed and installed below this repository's `.hermes-runtime/profiles/`.
- 9 independent loopback Gateways became healthy on ports 18100–18108; every runtime `.env` was mode 0600.
- The full 63-test suite passed, including failed Proposal rollback, partial Build-start cleanup, failed Gateway-start cleanup, and stale-PID ownership guards. A real Profile stop/start remained healthy with the ownership check enabled.
- Native update preserved Session, Memory, and `.env` marker files.
- Actual Hermes registry dispatch passed `task_id`, `session_id`, and Profile context to the async plugin handler; the handler contract returns a JSON string.
- Real `/v1/runs` and SSE produced `message.delta`, `reasoning.available`, and `run.completed`. The user-supplied Platform host produced a real upstream 429; the official DeepSeek API host completed with `OK`.
- Mini VOC no-call Run `2e6090774752441d88b8173e73c9c4b4` completed with no Span.
- Mini VOC baseline Run `08d5e57e50f54a3b889341d6ad396178` over-clarified. Review `34cc144e21ac402cbd8b2c15a9239ce4` produced evidence and uncertainty. Approved Proposal `ab46a0b077b24826a8a7e61e1ec0c13b` changed one Skill. Replay `1977c9892caf4b8f817f05c4c5b092ab` created a completed Product Span with a real child Hermes Run and cited `PRD-LOGIN-17`.
- Project Defense baseline Run `0347d407f02846d19acf73b98b9947b5` requested an unnecessary repository path. Review `098614ad21ae4c3a8bc986b58ca64c54` diagnosed the gap. An over-prescriptive Builder candidate was rejected as invalid; refined approved Proposal `ecbf251eeec947f788ef7474528f79a6` changed one Host Skill. Replay `247dc3aed22148809eb35d279bdefccb` created completed Source, Architecture, and Coach Spans.
- The real Hermes Dashboard discovered the user plugin and loaded the SDK-only bundle. Browser QA exercised Build, Apps, Playground saved-scenario population, and Review history; the native Profile link remained separate.
- Mini VOC post-change regression Run `e883a8f91e1345b9a72cf8d0d3790309` kept the vague-feedback behavior at zero Spans.

## Honest limitations

Project Defense Replay rejected the unsupported p99 figure but some architecture and recovery claims exceeded the inspected source. This is retained as evidence that Agent output still needs Review; it is not reported as a fully reliable answer. Session message export for one early Mini VOC trace returned an empty list, so its Review appropriately lowered root-cause confidence.

The test suite uses fake Hermes servers for deterministic failure, timeout, stop, nested Span, trace degradation, API, Review, Proposal, and Replay behavior. Real-model outputs remain stochastic and must not be treated as production quality metrics.
