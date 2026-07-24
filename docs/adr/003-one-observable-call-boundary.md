# ADR 003：唯一可观测调用边界

状态：已接受

所有需要被 Atelier 观测的跨 Profile 调用都使用 `atelier_call`。一个边界足以校验调用者身份和白名单，并关联真实父子 Sessions 与 Runs。

该工具不选择、排序、重试、聚合或解释专家；这些决定仍属于调用它的 Hermes Agent。
