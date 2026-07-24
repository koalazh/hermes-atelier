# ADR 001：Hermes 之上的薄层

状态：已接受

Hermes 负责 Profile 隔离与 Distribution、Agent 执行、工具、Memory、Sessions、Skills、Plugins、Gateways、Runs 和 Dashboard 管理。Atelier 只增加应用成员关系、可观测调用边界、跨 Profile 关联、本地批准状态与工作台 UI。

当 Hermes 原生提供可靠等价能力时，应删除对应 Atelier 接缝，而不是为兼容继续维护重复抽象。
