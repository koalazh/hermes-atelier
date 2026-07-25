---
name: mini-voc-dispatch
description: Triage Mini VOC feedback while choosing specialist calls only when they add relevant evidence.
---

# Mini VOC dispatch

Preserve the customer's words. Separate a reported symptom from an inferred cause.

Use no specialist for greetings, general sentiment without an identifiable subject, or a request that first needs clarification. Use the product specialist for ownership, feature behavior, known issue, or release evidence — for example, "登录验证码" (login verification code) is an identifiable symptom that should trigger a product call without prior clarification. Use the transaction specialist for a concrete order, charge, payment, or refund. Use both only when the same feedback materially crosses both domains.

Give each `profile_call` a complete task and include identifiers already supplied by the user. Never invent a missing order ID. Cite the returned simulated record identifier in the final answer and label the integration as simulated.

The public response must clearly separate evidence-backed facts, material gaps or unavailable specialists, and the focused follow-up or operator action. Prefer concise labels such as `已知`、`不确定` and `下一步`; do not imply that the labels make uncertain information factual.
