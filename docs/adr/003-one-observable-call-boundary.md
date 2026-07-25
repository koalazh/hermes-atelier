# ADR 003：唯一可观测调用边界

状态：已被 ADR 007 取代

V1 要求所有需要被 Atelier 观测的跨 Profile 调用使用 `atelier_call`。V2 不允许应用协作依赖 Studio，改用 App Pack 可选的独立 `profile_call`。

该工具不选择、排序、重试、聚合或解释专家；这些决定仍属于调用它的 Hermes Agent。
