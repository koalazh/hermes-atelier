# Trace model

A Hermes Session belongs to one Profile and contains that Agent's transcript. A Hermes Run is one execution in that Profile. An Atelier Run is only a correlation envelope for one multi-Profile application invocation; it never merges transcripts or replaces Hermes state.

The five core entities are `AtelierApp`, `AtelierRun`, `AtelierSpan`, `AtelierEvent`, and `AtelierReview`. Endpoint, Build, feedback, and Proposal rows support the approval lifecycle without becoming another runtime.

Root Session IDs are `at_<32-hex-run-id>_root`; child Session IDs are `at_<run-id>_<32-hex-span-id>`. The parser accepts only that form and verifies the recorded caller Profile and parent Span. Stable business Memory uses `X-Hermes-Session-Key` and is independent from transcript identity.

SSE is consumed while a Hermes Run is live because Hermes terminal records have finite retention. Events are redacted and written once to SQLite. No background JSONL mirror exists. Export creates an explicit frozen Trace Bundle with `manifest.json`, `events.jsonl`, referenced Session messages, feedback, application definition, and result.

If event persistence fails after a downstream call starts, the real downstream result is returned with `trace_degraded`. If authorization or the parent link cannot be durably established before dispatch, the call fails closed. A stop response means only that a stop request was sent until a terminal state proves cancellation.
