# V2.1 验证证据与已知限制

验证日期为 2026-07-25 至 2026-07-26。目标环境为本地 Hermes Agent 0.19.0；Hermes 核心只读使用，没有修改上游源码。本文取代旧 V2 验证记录，尤其撤销“为获得完整 Trace 而禁用业务 Profile delegation”的旧结论。

## 验证边界

V2.1 的默认路径是 Design → Coding Agent Handoff → Native Hermes Run → App Pack → HTTP Delivery。Runtime、Session、Memory、Profile 生命周期、Gateway 和模型路由仍由 Hermes 拥有。Attestation、Case、Experiment、Reviewer、候选 Git 绑定和 update/rollback 属于可选 Assurance Lab。

`allowed_calls` 在当前实现中有两层含义：wrapper 为每个目标生成独立 Gateway Key，调用方的 Runtime Mapping 只包含 self 与允许目标，正常 `profile_call` 路径因此具有目标级凭据边界；它不构成操作系统或网络层强隔离，拥有 terminal 或任意 HTTP 能力的 Agent 仍可能绕过工具策略。UI 和文档均将其称为 Tool Policy，不宣称完整 RBAC。

## 确定性门禁

最终回归使用仓库当前 `uv` 环境执行：

- `uv sync --extra dev`；
- `uv run pytest -q`：85 个测试通过；
- `uv run ruff check .`；
- Dashboard `index_v2.js` 执行 `node --check`；
- `uv build` 从 sdist 正常构建 wheel；
- `git diff --check`。

测试覆盖 Trace 慢/失败不阻塞业务、持续 SSE 也不能绕过总 timeout、timeout/cancellation 后 best-effort stop 及三态结果、Case 不改共享 Mapping、权限收缩移除旧 Key、合法 Agent ID 的 Key env 不碰撞、partial trace、configured/live attestation、损坏 evidence 文件不晋级、旧 Case policy 兼容、Single Profile Pack、非 `profile_call` Pack，以及 V1 模块不进入 V2 wheel。重复 attestation/probe 还会验证持久化 evidence level 不重复。

## 真实 Hermes smoke

四个 Pack 均从独立 release 目录安装到新的 `HERMES_HOME`，通过普通 Hermes Gateway 和 OpenAI-compatible HTTP 调用，而非 Dashboard 代理：

| Pack | 实例 | 结果 |
| --- | --- | --- |
| Mini VOC | `voc-v21` | 4/4 Cases 通过；Product 与 Transaction Trace 可见；引用样例记录 `PRD-LOGIN-17` |
| Project Defense | `defense-v21` | 3/3 Cases 通过；拒绝无源码依据的 p99 数字 |
| Single Profile Hello | `single-v21` | 1/1 Case 通过；`allowed_calls` 为空；未安装 `profile_call`；HTTP 返回问候 |
| Delegation Note | `delegation-v21` | 1/1 Case 通过；真实使用 Hermes 原生 `delegate_task`；不依赖 `profile_call` |

四个实例的 `configured_runtime_attestation` 和 `live_runtime_probe` 均成功。live probe 从 `/health`、`/health/detailed`、`/v1/capabilities` 和 `/v1/models` 确认 Hermes 0.19.0 与可见能力；Hermes 当前接口不能独立证明 Profile identity，因此该字段明确为 `unverified`。

Mini VOC 的 product Profile 使用 Hermes 原生命令临时覆盖为 `deepseek-chat`。重新 attestation 后，dispatcher/transaction 保持 wrapper 默认模型，product 记录原生覆盖及 `matches_wrapper_record=false`；随后恢复原配置。这证明 Manifest 没有承担 per-Agent 模型平台职责。

Dashboard 未启动且 release 目录中没有 `.atelier`、Builder、Drafter 或 Reviewer 时，四个 Pack 仍可通过 HTTP 工作。发布应用因此不依赖 Atelier。验证完成后只清理本任务创建的服务和运行目录，不触碰用户既有 Studio 数据。

## P0 运行边界

在真实 `profile_call` 链路中验证：

- Trace Sink 故意延迟 5 秒时，业务调用成功且 `trace_degraded=true`；独立 0.2 秒 Trace timeout 没有等待 Sink 完成；持续产生 SSE 的子 Run 也受总 deadline 限制；
- Trace Sink 不可连接时，业务调用仍成功且明确降级；
- 目标 Run timeout 为 1 秒时，调用方约 1.1 秒返回错误并报告 `stop_requested`，没有把已发送请求伪装成 `stop_confirmed`；
- 单测另外覆盖 caller cancellation、SSE 断开、网络错误和事件解析失败后的 stop；
- Case 前后所有 Profile 的 `local/app-runtime.json` mtime 不变。Case 从实例固定 Trace directory 按 `source_session_id` 分文件读取，不改共享 Runtime Mapping。

## Builder 与实现交接

真实 Builder 使用同一 Hermes Session 进行多轮需求对齐。首次生成暴露了两个实际问题：Profile 中 `${ATELIER_MODEL}` 不会被 launchd Gateway 按预期解析，且 provider HTTP 错误可能被误报为缺少 `DESIGN_STATUS`。修复后 Builder/Drafter/Reviewer 不再携带 Atelier 统一模型配置，模型由 Hermes 原生 Profile 配置拥有；provider 4xx/5xx 会直接呈现。

最终 Design `f808e1d189804077b35db043381211e7` 达到 `plan_ready`，同时输出 `PLAN.md` 与 `IMPLEMENTATION_HANDOFF.md`。handoff 包含原始需求、对齐目标、Profile 边界、工具/权限、Session/Memory/Skill 归属、推荐协作原语、Pack 与 HTTP 边界、Cases、未接入系统和非目标，并通过冻结 V2 schema 检查。历史 Design `447e45d94b1144689f0d2ac9bf6b1015` 可从 Dashboard 恢复，即使当前 Builder Gateway/Secret 不可用；新 Design 的 Start 操作会直接发送原始需求，不要求用户重复一次。

默认动作是 Export handoff；Generate with Hermes 是可选 Drafter 路径。Drafter 的 `terminal.cwd` 明确不是安全沙箱，输出仍须经过 App Pack Validator，且不会自动安装、采纳或提交。Reviewer 同样只在 Assurance Lab 中可选运行。

## Dashboard 浏览器验收

真实 Hermes Dashboard 挂载 Atelier 用户插件后，浏览器可见验收确认：

- 选择四个 App Pack 并进入以 Pack 为中心的六区工作空间；
- Overview 自动发现 `delegation-v21`，展示从 `packed` 到 `fresh_verified` 的证据阶梯；
- Design 默认 Export handoff，并可恢复历史 Design；
- Core 与 Assurance Lab 在导航和操作上分区；
- 页面 console 无 warning/error。

真实 workspace API 还确认四个 Pack 会自动发现实例和最近 Sessions。初轮验收曾向 Studio Store 人工写入一条事件来检查 `partial_trace` 文案；独立完成检视指出这不能证明 Lens 接通 App Pack 的实例 Trace，因此不计作最终运行证据。修复后 Session API 携带自动发现的 instance，并由回归测试从该实例真实哈希 Trace 文件读到 `partial_trace`；文案继续明确原生 delegation、Kanban 或 MCP 协作可能不可见。恢复浏览器时 Chromium 落入 `ERR_CONNECTION_REFUSED` 数据页，浏览器控制策略禁止以脚本 URL 或其他浏览器表面绕过，因此本轮没有伪造“再次点击 Sessions 页”的可见证据；浏览器已确认的可见范围与修复后 API/确定性验证范围在这里分别记录。

## 对抗式检视后的定向复验

四位独立审查者发现的 12 个 P1 全部修复，详见 `V2_1_COMPLETION_REVIEW.md`。从修复后干净提交新建 Single Profile release，在全新 `HERMES_HOME` 使用摘要化独立 Key env 完成 install、configure、start、普通 OpenAI-compatible HTTP、configured attestation、live probe 和 1/1 Case；evidence ladder 达到 `fresh_verified`，Profile identity 仍诚实标为 `unverified`。随后停止并卸载本任务全部 Gateway/launchd 条目和 Dashboard，删除任务 runtime、临时 release 与人工 Trace；用户既有 `.atelier` Design/Experiment 数据未删除。

## Schema、状态与发布语义

- App Pack schema 保持 V2 冻结，没有加入模型、端口、Secret、部署或 Workflow 字段；Pydantic 继续 `extra="forbid"`；递归理念关键词黑名单已删除。`calls.forbidden` 仅兼容读取：观察到可判失败，未观察到只能 `unverified`，不能因 Trace 缺失而假通过。
- 新写入使用 `new_session`、`retained_scope`、`fresh_instance` 和 `evaluation_context`；旧 `clean`、`session_only`、`retained`、`initial_state` 仅兼容读取。
- `new_session` 只承诺新 Hermes Session；只有新物理 Profile/HERMES_HOME 才能形成 `fresh_instance`。
- evidence ladder 为 `packed → installed → configured → runtime_attested → live_probed → cases_passed → fresh_verified`，不要求每级都存在，也不把 Pack 称为 Validated release。
- update/rollback 保留为 local、best-effort、experimental；没有事务原子、远程发布、蓝绿、流量切换或多主机承诺。

## 发布包与 V1

正常 `uv build` 先生成 sdist，再从 sdist 生成 wheel。回归检查 wheel 包含活动的 Atelier、profile_call 与 Dashboard 资产，不包含已退出活动路径的 V1 compatibility 模块及其旧状态机测试；V1 历史继续由 Git tag/history 保留。

## 已知限制

- 模型输出具有随机性；真实 smoke 证明链路和当前样例可执行，不证明未来每次回答相同。
- Prompt、Case 和 Reviewer 不能证明模型永不虚构；肯定性业务主张仍需来源证据。
- Trace 是可选开发观测，不是完整审计。`partial_trace` 或无 Trace 都不能证明没有协作。
- `allowed_calls` 的独立 Key/Mapping 约束正常工具路径，不是 OS、网络或企业 RBAC。
- `configured_runtime_attestation` 证明配置记录与安装资产；只有 live probe 才证明当时可访问的运行信息，仍无法确认的字段为 `unverified`。
- 当前每物理 Profile 一个 loopback Gateway 是 Hermes 0.19 Plugin 隔离能力下的实现，不是 Atelier Runtime。
- update/rollback 不是生产部署系统。
- Atelier 不提供通用 Chat、任务队列、Workflow、模型管理、远程 Registry、生产 Mesh 或多租户发布平台。
