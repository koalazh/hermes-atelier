# Delegation Note

这是非 `profile_call` 协作反例。它保留 Hermes 原生 delegation，不新增 App Pack
协作协议字段，也不要求 Atelier 能观察完整调用树。Lens 没有 `profile_call` 事件时
必须显示 `unobserved_collaboration_possible`，不能断言“没有协作”。
