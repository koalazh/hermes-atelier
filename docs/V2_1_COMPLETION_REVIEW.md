# V2.1 对抗式完成检视

检视日期：2026-07-26。四轮检视分别由独立子 Agent 在实现提交 `8d85e31` 上只读执行，主 Agent 只根据可复现发现修改。高优先级修复集中在 `b576f76`，随后重新执行确定性门禁和真实 Hermes 定向 smoke。

## 结论

四位审查者均未发现 P0。共发现 12 个 P1；全部修复并增加回归。剩余建议均为 P2/P3 的渐进体验或兼容清理，不阻塞 V2.1 主路径，也不值得为本次再增加协议或状态。

相对重构前 `4c5a7d8`，当前变更为 127 个文件、3030 行增加、6020 行删除，净删除 2990 行。没有新增 Runtime、后台服务、消息队列、Workflow、RBAC 或部署平台；App Pack schema 仍为冻结 V2。

## 1. 极简主义审查

审查者重点追踪活动调用链和 wheel 内容，发现：

- P1：Dashboard Lens 读取 Studio Trace，而 App Pack 实际写实例固定 Trace directory。已改为 Session 查询携带自动发现的 instance，直接读取同一哈希分区文件；显式 HTTP/Studio Sink 仅保留兼容和 Experiment fallback，不再是默认 Lens 来源。
- P1：`AppPack.runtime_mapping()` 是仅被测试调用的旧全 Agent/统一 Key 协议。已删除方法和旧测试；唯一活动 mapping 由 `PackRuntime.configure()` 生成。
- P2（按影响提升修复）：Builder 在缺少 handoff separator 时生成大段泛化 fallback。已删除 fallback；`PLAN_READY` 缺独立 PLAN/handoff 会明确失败并要求同一 Session 修正。
- P3：overview 仍聚合前端不用的全局 instance/design/experiment，另有重复 Cases endpoint。两者均已删除。

复核结论：Core/Lab 分层没有引入新平台概念；活动 Trace 所有权和 mapping 协议已经收敛。

## 2. Agent 自主性审查

审查者确认业务 Profiles 不再因 Trace 禁用 delegation，Builder/Reviewer 的禁用分别基于规划副作用和只读证据边界。发现：

- P1：`calls.forbidden` 会把“Trace 中没看见”当作通过。现在观察到目标可确定失败；未观察到返回 `verified=false`、`passed=false`，原因明确为可选 Trace 无法证明缺席。
- P2（已修复）：Mini VOC clarify/product 和 Project Defense coach-only 用 forbidden 规定普通质量路线。已删除这些断言，保留输出、可信数据边界所需的 positive required 和 human review。
- P2（与极简审查同源）：Lens 没接实例 Trace。已修复。

复核结论：`complete_trace` 只表示已开始的可见 `profile_call` 都有终态，不代表完整协作；`partial_trace` 和 `unobserved_collaboration_possible` 均不会被解释为没有 delegation、Kanban、MCP 或直接协作。

## 3. 安全与可靠性审查

审查者用独立临时环境复现五个 P1：

1. allowed_calls 收缩后旧目标 Key 留在调用方 `.env`。configure 现在清理当前及上一 wrapper Key 命名空间，只写 self 与当前允许目标；attestation 还会拒绝意外 managed Key。
2. 合法逻辑 ID `foo-bar`/`foo_bar` 的 env 名碰撞。Key env 现在加入 logical ID 的稳定 SHA-256 短摘要。
3. `timeout_seconds` 只有 HTTP read inactivity 语义，持续 SSE 可无限运行。取得子 Run 后，整个 events/status 生命周期现在受 `asyncio.timeout` 总 deadline；超时进入既有 best-effort stop 三态。
4. Experiment 只冻结 wrapper 顶层模型。现在保存并在 Trial 前后比较每个 Profile 的 `model_configuration` 与 `config_sha256`。
5. evidence ladder 只按文件存在晋级且写入非原子。写入改为同目录临时文件原子 replace；读取校验 kind、verified/passed、instance 与当前 pack revision，损坏或过期文件不晋级。

复核结论：Case 固定 Trace directory 不改共享 Mapping；Trace HTTP 短 timeout 仍与业务 client 分离；stop 三态没有把请求中误写成已停止；update/rollback 仍是 local、best-effort、experimental。

## 4. 开发者体验审查

审查者按“需求 → handoff → Pack → Hermes Run → 证据 → HTTP”从零走查，发现四个 P1：

- Start Design 只建记录，用户必须再次发送才会启动 Builder。create API 现在直接开始首轮 Builder，并在消息中展示原始需求。
- 恢复历史 Design 也强制要求当前 Builder URL/Secret。只读 detail 现在不构造运行客户端，Builder 关闭仍可读取 PLAN/handoff。
- 自动发现 Session 后 Lens 仍读错 Trace。已接入自动发现实例的固定 Trace directory。
- Delivery 只显示通常无法执行的 `./app install`。页面现在使用自动发现/刚创建的 release 绝对路径，展示 `cd`、consumer HERMES_HOME、Secret 占位、install/configure/start/status 和 HTTP curl；无法推导的模型、Base URL、Secret 值与空闲端口明确保留为 Consumer 输入。

复核结论：普通 Demo 不需要先进入 Assurance Lab；Design 默认 Export handoff，Drafter/Reviewer 均为可选动作；Pack、实例、entry URL、Session、Cases、release 与证据等级可自动发现。

## 剩余非阻塞建议

- 多个 configured instance 同时存在时，Sessions 当前选择排序后的第一个；后续可在已有实例列表上增加选择器，无需新协议。
- Native Chat 链接当前打开 `/chat`，没有预填 entry Profile/Session；应在确认 Hermes Dashboard 稳定 query contract 后再接入，避免固化猜测 URL。
- Design 目前是项目级、未绑定 Pack，所有 Pack workspace 都会显示为 global history。等真实多 Pack 设计管理需求出现后再增加最小绑定，不在本次扩 schema/state。
- Coding Agent 输出需落在项目 `apps/<pack-id>` 才会自动发现；handoff 已规定 App Pack 边界，但 UI 可在后续增加 Refresh/发现目录提示和命令 Copy 反馈。
- 显式 `POST /traces` 与 Studio Trace Store 暂留为已有 HTTP Sink/Experiment 兼容；默认 App Pack Lens 已不依赖它。确认无外部 Consumer 后可单独移除。

## 修复后证据

- 85 个 pytest 通过，Ruff、Dashboard `node --check`、`uv build`、`git diff --check` 通过。
- 从修复后干净 HEAD 创建新的 Single Profile release，在全新 HERMES_HOME 完成 install/configure/start、普通 OpenAI-compatible HTTP、configured attestation、live probe 和 1/1 Case；证据阶梯达到 `fresh_verified`。
- Completion Challenge 首轮指出修复后的实例 Trace 尚缺真实浏览器 oracle。随后从当前 HEAD 重新安装 Mini VOC，创建普通 Hermes Session 和真实完整/未完成 `profile_call` 事件；浏览器自动发现实例和最近 Session，无需复制 ID 即显示 `partial_trace`、started/completed 事件及“其他原生协作可能不可见”提示，console 无 warning/error。
- 新 `.env` 只有 self 的摘要 Key env；live probe 对无法证明的 Profile identity 继续报告 `unverified`。
- 所有本任务 Gateway、launchd 条目、Dashboard、临时 runtime/release 和人工 Lens Trace 已停止或删除；用户已有 `.atelier` Design/Experiment 数据未删除。

## 最终判断

V2.1 达到完成条件：Core 默认路径更短，Assurance Lab 可选，Hermes 持续拥有 Runtime，Agent 原生协作不受 Trace 塑造，发布应用脱离 Atelier，Schema 未扩张，两个反例 Pack 和两个现有应用均已验证。高优先级审查问题已经关闭；剩余建议不改变安全承诺或主路径，不应在本次被扩展成新制度。
