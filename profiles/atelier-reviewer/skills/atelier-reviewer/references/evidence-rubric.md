# Evidence rubric

Strong evidence identifies an immutable bundle artifact and a concrete Run, Span, Session, Hermes Run, event, message, scenario assertion, or human feedback item.

Use these labels:

- 事实: directly present in the frozen bundle;
- 推断: a plausible explanation consistent with facts, with alternatives retained;
- 建议: the smallest candidate change worth testing;
- 尚缺证据: information required before raising confidence or broadening the change.

Do not infer hidden reasoning from a final answer. Do not equate a timeout with poor expert quality. Do not treat a mocked tool as a real integration. Do not change the scenario or evaluator to make the candidate pass. Require replay of the same scenario and compare output, calls, errors, latency, and human judgment.

