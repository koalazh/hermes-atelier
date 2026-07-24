# 验证证据与已知限制

验证日期为 2026-07-24，目标环境是 Hermes Agent 0.19.0（`2026.7.20`，commit `9eb7b1a6b1ffdd4ad1a85aee3f38edceee2b927f`）。Hermes 上游 checkout 只读使用，并保留其原有未提交改动。

## 自动化验证

- 完整 71 项测试通过，包括 schema、路径、脱敏、SQLite、Profile 生命周期、Hermes HTTP、Run/Span、Dashboard API、启动脚本、Build、Review、Proposal、Replay、文档约束和失败恢复。
- `tests/test_full_workflow.py` 使用真实 Atelier Store 与 Services，把 `Build → Run → Observe → Review → Propose → Approve → Replay` 串在同一个临时应用与 SQLite 状态源中；只替换外部 Hermes HTTP/Profile 进程边界。
- 失败路径覆盖 Proposal 源码/Profile 回滚、Build 部分启动清理、Gateway 启动失败清理、过期 PID 所有权校验、Run 失败/超时/停止、多层 Span 和 Trace 降级。
- Ruff、Dashboard bundle JavaScript 语法检查和 Python sdist/wheel 构建通过。

## 当前 Hermes 真实能力证据

- 9 个原生 Profile Distributions 已安装到当前仓库 `.hermes-runtime/profiles/`。
- 9 个独立 loopback Gateways 曾在 18100–18108 端口全部健康；每个运行态 `.env` 权限为 `0600`。
- 原生 Profile update 保留了 Session、Memory 与 `.env` marker 文件。
- Hermes registry 实际 dispatch 向 async Plugin handler 传入 `task_id`、`session_id` 与 Profile 上下文；handler 合同返回 JSON 字符串。
- 真实 `/v1/runs` 与 SSE 产生 `message.delta`、`reasoning.available` 和 `run.completed`。
- 新增 PID 所有权保护后，真实 Profile stop/start 仍恢复为 healthy。
- 真实 Hermes Dashboard 发现并加载了 SDK-only Atelier bundle。浏览器 QA 检查了 Build、Apps、Playground 保存场景填充和 Review 历史，原生 Profile 管理链接仍保持独立。
- 前台 Dashboard 生命周期已实测：`Ctrl+C` 后 9122 端口关闭、脚本无 traceback，9 个业务 Profile Gateways 仍全部 healthy；随后 `scripts/stop.py` 将它们全部停止。

## Mini VOC 闭环

- 无需专家的 Run `2e6090774752441d88b8173e73c9c4b4` 完成且没有 Span。
- 基线 Run `08d5e57e50f54a3b889341d6ad396178` 出现过度追问。
- Review `34cc144e21ac402cbd8b2c15a9239ce4` 输出了证据与不确定性。
- 明确批准的 Proposal `ab46a0b077b24826a8a7e61e1ec0c13b` 只修改一处 Skill。
- Replay `1977c9892caf4b8f817f05c4c5b092ab` 创建了真实 Product 子 Hermes Run 和完成 Span，并引用 `PRD-LOGIN-17`。
- 改动后的模糊反馈回归 Run `e883a8f91e1345b9a72cf8d0d3790309` 仍保持零 Span 行为。
- 后续真实复验中，Run `c6e3629eacdc4d90a19e991b670e5774` 再次验证模糊输入零 Span；Run `ffd8bb32afff4cf4806e41110d72fe3f` 同时创建完成的 Product 与 Transaction Spans，并保持两类模拟证据分离。

## Project Defense 闭环

- 基线 Run `0347d407f02846d19acf73b98b9947b5` 不必要地要求用户提供仓库路径。
- Review `098614ad21ae4c3a8bc986b58ca64c54` 诊断了该缺口。
- 第一版过度规定流程的 Builder 候选被判为无效；精简 Proposal `ecbf251eeec947f788ef7474528f79a6` 经明确批准，只修改一处 Host Skill。
- Replay `247dc3aed22148809eb35d279bdefccb` 创建了完成的 Source、Architecture 和 Coach Spans。
- 后续复验发现 `evidence-gap` 的稳定 `memory_scope` 会让 Host 复用旧结论并跳过本次取证，因此将长期 Memory 收敛到 `coach-only` 场景。修正后 Run `1d69d929e49b443b972f21484b6c74d3` 使用新的 definition revision，创建完成的 Source Span，拒绝无依据的 60% p99 声明，且不再引入无测量支持的数值性能区间。

## 模型端点记录

用户提供的 Platform host 在真实 smoke 中返回上游 HTTP 429。改用 DeepSeek 官方 API host 后，同一 Hermes Runs/SSE 链路成功返回 `OK`。该事实只说明端点链路可用，不代表模型输出质量。

## 已知限制

Project Defense Replay 拒绝了无依据的 p99 数字，但部分架构与恢复描述仍超出已检查源码。该结果被保留为“Agent 输出仍需 Review”的真实证据，而不是完整可靠答案。

一次早期 Mini VOC Trace 的 Session messages 导出返回空列表，因此对应 Review 正确降低了根因置信度。确定性测试使用 fake Hermes Server 验证控制流；真实模型输出仍有随机性，不能转化为生产质量指标。
