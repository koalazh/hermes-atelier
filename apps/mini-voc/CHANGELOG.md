# Mini VOC 变更记录

## 2.1.0

- Case 使用诚实的 `new_session` 语义；
- 不再仅因 Trace 禁用 Hermes delegation；
- configure 使用逐目标 Key 与最小 runtime mapping；
- 保持 App Pack Schema V2 不变。

## 2.0.0

- 迁移到 V2 逻辑 Agent Manifest 和独立 App Pack；
- 入口改为 Hermes 原生 OpenAI 兼容 API；
- 使用独立 `profile_call` 调用 Product/Transaction；
- Scenario 迁移为无 Workflow 的 Case；
- 添加半结构化业务输出约束、安装说明和示例客户端；
- 明确所有业务记录均为模拟数据。
