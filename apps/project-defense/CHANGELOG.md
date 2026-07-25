# Project Defense 变更记录

## 2.1.0

- Case 使用 `new_session` / `retained_scope` 语义；
- 不再仅因 Trace 禁用 Hermes delegation；
- configure 使用逐目标 Key 与最小 runtime mapping；
- 保持 App Pack Schema V2 不变。

## 2.0.0

- 迁移到逻辑 Agent App Pack 和 Hermes 原生 Session/Run；
- `source` 示例源码改为 Distribution 自有资产，不再读取主工程路径；
- 使用独立 `profile_call`，入口自主决定 Source/Architecture/Coach；
- 将长期 Memory 收敛为 Consumer 显式 caller scope；
- Scenario 迁移为 Case，增加证据缺口与表达边界验证；
- 添加 fresh 安装、原生命令和多轮客户端。
