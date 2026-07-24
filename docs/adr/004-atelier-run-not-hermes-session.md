# ADR 004：Atelier Run 不是 Hermes Session

状态：已接受

每个 Profile 保持自己的 Hermes transcript Session 与 execution Run。Atelier Run 只关联这些独立对象，不复制或合并 Session。

Transcript Session ID 对每次 Atelier Run 唯一；长期 Memory Key 与它分离，Atelier 不把 Session 内容复制进自己的权威状态库。
