# ADR 001：Hermes 之上的薄层

状态：已接受

Hermes 负责 Profile 隔离与 Distribution、Agent 执行、工具、Memory、Sessions、Skills、Plugins、Gateways、Runs 和 Dashboard 管理。Atelier 只增加多轮设计证据、可选 Trace 索引、Case/Experiment、App Pack 验证与工作台 UI；应用成员关系随 Pack 交付，不进入 Atelier Runtime。

当 Hermes 原生提供可靠等价能力时，应删除对应 Atelier 接缝，而不是为兼容继续维护重复抽象。
