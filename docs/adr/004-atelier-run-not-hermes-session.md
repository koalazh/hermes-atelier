# ADR 004：Atelier Run 不是 Hermes Session

状态：已被 ADR 007 取代

每个 Profile 保持自己的 Hermes transcript Session 与 execution Run。V2 删除 Atelier Run 信封，仅以可选 Trace 索引关联真实 `profile_call`。

长期 Memory Key 与 Hermes Session ID 分离；Atelier 不复制 Session 内容，也不建立运行权威状态库。
