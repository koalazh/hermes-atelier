# Hermes Atelier V2.1 核心收敛审计

> 审计日期：2026-07-25  
> 审计基线：`main` / `4c5a7d8`，初始工作树干净且与 `origin/main` 对齐  
> Hermes：本地安装 `0.19.0 (2026.7.20)`，upstream `9eb7b1a6`，只读审计  
> 结论性质：本文先记录当前事实、调用链和 V2.1 取舍；本文提交前不修改产品行为。

## 1. 审计范围和方法

本轮重新检查了：

- `b89c1fc` V2 边界审计之后到 `4c5a7d8` 的 14 个提交；
- `plugin/atelier/`、`plugin/profile_call/`、Builder/Drafter/Reviewer；
- App Pack、Case、Experiment、configured runtime 证明、release/update wrapper；
- Dashboard V2 bundle 和 API；
- Mini VOC、Project Defense 的 Manifest、Profile config、Case、INSTALL；
- 当前 115 个测试、`docs/VALIDATION.md`、sdist/wheel 内容；
- Hermes 0.19.0 CLI 与只读源码中的 `/health`、`/health/detailed`、
  `/v1/capabilities`、Sessions、Runs、SSE 和 stop 行为。

确定性行为基线通过：

```text
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv build
```

结果是 115 tests、Ruff、sdist/wheel build 均通过。这个结果只说明 V2 当前实现自洽，
不证明 V2.1 的目标已经满足。

## 2. 上次方案后的真实变化

`b89c1fc` 之后不是简单增量，而是完成了 V2 App Pack runtime、native Session
Studio、两个真实应用交付，并经历三轮 trust-boundary 修复：

- `profile_call` 已从 Atelier runtime 分离；
- Builder 改为 Hermes 原生 Session，多轮对齐与 Drafter 分权；
- release 固化完整文件、Case、Contract、source provenance；
- wrapper 实现 install/configure/gateway/cases/attest/update/rollback；
- Candidate 绑定真实 Git worktree/commit/baseline；
- Secret、symlink、路径逃逸、安装回执变换和 rollback 经过负向回归；
- Mini VOC 与 Project Defense 已在 fresh `HERMES_HOME` 中完成过真实 HTTP smoke。

因此 V2.1 不应重写 provenance、路径、Secret、install receipt、Git binding 或
update rollback。真正需要改变的是这些能力在产品中的默认位置、证据命名，以及
Trace/Case/Key 的运行边界。

## 3. 当前从业务需求到 HTTP 交付的真实用户路径

当前真实路径不是 README 顶部的六行概念，而是：

1. 开发者先自行安装并启动 Builder Gateway，向 Dashboard 注入
   `ATELIER_BUILDER_URL` 和 Key；若要 Draft/Review，还要另行安装、启动和配置
   Drafter/Reviewer。
2. Dashboard `Design` 创建 Design，后端创建 `.atelier/v2/designs/<id>`，再通过
   Hermes `/api/sessions/{id}/chat` 复用 Builder Session。
3. Builder 只能产生 `PLAN.md`。当前 UI 的主按钮是 `Generate Draft`，没有默认
   `IMPLEMENTATION_HANDOFF.md` 导出，因此用户被引导进入 Hermes Drafter。
4. Drafter 使用 `/v1/runs` 在 `terminal.cwd` 指向的 Draft 目录写文件；这个 cwd
   是工作目录约束，不是 OS sandbox。后端只在完成后用 `AppPack.load()` 验证一个
   `app.yaml`，不会 adopt/install/commit。
5. 用户需要把 Draft 或人工实现放入 `apps/<id>`，然后运行
   `atelier validate`、`atelier release`。release 复制 Pack、按需注入独立
   `profile_call`、生成 `app.lock` 和薄 `./app`。
6. Consumer 进入 release 目录，设置 `HERMES_HOME`、模型 Key 和统一 Gateway
   Key，执行 `./app install/configure/start`。wrapper 为每个物理 Profile 启动
   Hermes 原生 Gateway。
7. 下游以普通 OpenAI-compatible HTTP 调用 entry Profile；Atelier、`.atelier`
   和三个工坊 Profile 都不在请求链上。
8. 若要观察，用户回到 Dashboard `Run & Observe`，手工复制 Session ID。
9. 若要 Experiment，用户再手工输入 runtime instance；后端先执行 attestation，
   再运行 Case/Trial，可选调用 Reviewer。

核心交付链在第 6–7 步已经成功脱离 Atelier；主要摩擦集中在第 1、3、8、9 步。

## 4. V2.1 产品分层

### 4.1 Hermes Atelier Core

Core 只保留日常开发路径：

```text
Design → Coding Agent Handoff → Native Hermes Run → App Pack → HTTP Delivery
```

Core 的职责是：

- Builder 多轮目标对齐；
- 同步生成 `PLAN.md` 和 `IMPLEMENTATION_HANDOFF.md`；
- 默认导出 handoff 给任意 Coding Agent 或人工；
- App Pack 自动发现、schema 验证、分组和 selected-pack workspace；
- 链接 Hermes 原生 Chat，发现最近 entry Sessions，展示可见证据；
- 展示 pack、install/configure、HTTP 示例、当前 evidence level 和限制。

Core 不要求 Drafter、Reviewer、Experiment、Candidate 或 attestation 才能创建 Demo。

### 4.2 可选 Assurance Lab

以下实现保留，但从默认路径移到 selected-pack 的 `Assurance Lab`：

- configured runtime attestation 和 live probe；
- Case runner、Experiment、多 Trial；
- Candidate Git binding；
- Reviewer 和 evidence bundle；
- release provenance、Secret/supply-chain 检查；
- update/rollback evidence。

它们的产品定位是“提高证据等级”，不是“应用才能运行”。update/rollback 继续保留为
local、best-effort、experimental，不扩展成部署平台。

### 4.3 独立运行时原语

`plugin/profile_call` 是随需要它的 App Pack 分发的 Hermes Plugin。它不导入
Atelier、不读 `.atelier`，也不属于 Atelier Runtime。Hermes 原生能力足够时应替换
它，而不是让 Atelier 围绕它扩张协议。

## 5. 必须由 Hermes 原生承担的能力

Hermes 0.19.0 已实际提供：

- Profile Distribution install/update 与逐 Profile config；
- Gateway 生命周期、健康、PID 和后台服务；
- `/api/sessions`、历史 messages、fork、同步/流式 Chat；
- `/v1/runs`、状态、SSE、approval、stop；
- `/v1/chat/completions`、`/v1/responses`；
- `/v1/capabilities`、`/v1/models`、`/v1/toolsets`、`/v1/skills`；
- delegation、Kanban、Memory、Skills、Plugins 和工具执行。

因此 Atelier 不实现 Agent Loop、Session/Chat、Memory、Profile 生命周期、Gateway
Supervisor、PID、模型路由、任务队列、Workflow 或部署。Dashboard 只链接/读取
Hermes 原生资源。

Hermes 当前仍有两个相关限制：

1. multiplex Gateway 的 Plugin Manager 不是 Profile-scoped，带不同业务 Plugin 的
   Profiles 仍需独立 loopback Gateway；
2. `/v1/capabilities` 能确认 API surface、server runtime 和配置模型，但不直接声明
   当前逻辑 App Agent ID。Profile identity 只能由安装映射、目标 URL 与 Consumer
   配置交叉确认；不能从 health 响应猜测。

## 6. 当前复杂度分类

### 6.1 解决真实问题，必须保留

- App Pack 逻辑 ID 与安装时物理 Profile 映射；
- 唯一 public entry 与 Distribution/path/symlink 边界；
- Pydantic `extra="forbid"` 和显式 schema；
- release staging、完整文件 digest、`app.lock`；
- Git/content provenance、Candidate worktree/commit/baseline 复验；
- Secret/credential shape、运行态文件过滤、`.env` 0600；
- Hermes install 会改写 `distribution.yaml`、configure 会改写 `config.yaml` 的
  两类显式 runtime transform；
- instance/state root containment；
- update 失败的 best-effort rollback 与负向测试；
- Case/Contract hash、Experiment 条件冻结；
- `profile_call` dispatch 前 fail-closed，业务完成后 Trace 失败只降级；
- Project Defense 自有 caller-scope state Plugin，不把 Hermes 全局 Memory 冒充
  caller isolation。

这些都由真实 smoke、失败或独立审查发现，不应因“核心收敛”而删除。

### 6.2 主要服务于证明系统本身，应移到 Lab 或降级

- Dashboard 默认要求先理解 revision、model fingerprint、runtime attestation、
  Experiment、Trial、Candidate；
- 把 `Generate Draft` 作为 Builder ready 后唯一显眼动作；
- 把 Reviewer 绑定为 Experiment 后的产品叙事，而不是可选 evidence consumer；
- 把仅完成 pack/release staging 的结果称为 `Validated releases`；
- 普通 Case 普遍用 `calls.required` 证明 Agent 走了预期专家路线；
- 为收集 Case Trace 临时改写每个 Profile 的共享 mapping；
- 为了 Trace 可见性在所有业务 Profile 禁用 delegation；
- 对 `app.yaml` 和 Case 任意嵌套内容递归执行设计哲学关键词黑名单。

## 7. 限制 Agent 自主行为的实现

### 7.1 delegation 被观测能力反向关闭

Mini VOC 三个业务 Profile、Project Defense 四个业务 Profile都禁用 delegation。
历史记录明确说明直接诱因是一次 Host 使用 delegation 后没有 `profile_call` Trace，
随后测试又固定所有 Profile 必须禁用 delegation。这不是权限、数据或工作目录边界，
而是观测协议塑造行为，应撤销。

Builder/Reviewer 的 delegation 禁用可以保留：前者是避免规划阶段产生外部副作用，
后者是冻结 evidence 的只读审查边界。Source 的 terminal/project 禁用、业务专家的
file/code/Memory 禁用也有明确数据或状态边界，应按 Profile 逐项保留。

### 7.2 Case 把调用路线当成正确性

当前 7 个 Case 中，Mini VOC `product`、`cross-domain`、`expert-failure` 和
Project Defense `evidence-gap` 使用 `calls.required`。其中要求可信数据必须由唯一
受权专家获取时可以保留；如果输出合同已能验证可信证据，则 required call 只是固定
路线，应降级到 human review 或删除。`forbidden` 只有在越权、数据边界或明确“不核查”
合同下才有意义。

### 7.3 递归关键词黑名单固化设计偏好

`AppPack.load()` 和 `load_case()` 会在所有嵌套 dict/list 中拒绝 `workflow`、
`parallel`、`fan_out`、`aggregate`、`judge` 等 key。它会拒绝业务 Plugin 的自然
配置或测试数据，即使 Atelier 根本不执行这些内容。V2.1 删除递归扫描，继续依赖
Manifest/Case `extra="forbid"`；Atelier 不新增 Workflow executor。

## 8. P0 运行边界根因

### 8.1 Trace 会延迟业务 dispatch

`ProfileCaller.call()` 当前只创建一个 `httpx.AsyncClient(timeout=业务 timeout)`，
先 `await _emit_trace(started)`，再 POST 目标 `/v1/runs`。同一个 Client 和最长
120 秒 timeout 也用于 Trace URL，所以慢 Sink 会直接延迟 dispatch。

V2.1 使用独立 Trace Client 和极短 timeout；started 失败立即继续，completed 失败
不改变业务结果，文件失败只设置降级。无需队列或后台服务。

### 8.2 异常会留下孤儿子 Run

目标 `/v1/runs` 返回 `run_id` 后，SSE timeout、caller cancellation、断线、网络错
或 JSON 解析错没有 finally/except stop。Hermes 0.19.0 的 stop endpoint 会先返回
`{"status":"stopping"}`；这只能证明 `stop_requested`，不能证明 Run 已停止。

V2.1 在拥有 `run_id` 后对异常 best-effort stop，并将结果区分为：

- `stop_requested`：Hermes 接受，当前只确认 `stopping`；
- `stop_confirmed`：后续状态已是 `cancelled`/终态；
- `stop_unknown`：stop 请求或确认失败。

caller cancellation 仍向上游传播，但先 shield 一次有界 stop。

### 8.3 Case 会改写共享 mapping

`PackRuntime._run_case()` 当前备份所有 `local/app-runtime.json`，逐个写入同一临时
Trace file，执行后恢复。并发 Case、普通业务请求和进程崩溃都会破坏这个假设。

Dashboard Experiment 还有另一处不一致：它直接发 entry Run，再从 Studio Store 读取
Trace，但普通 configure 没有配置 Studio Trace Sink。测试中的 fake client 会直接向
Store 追加事件，真实默认部署不会。因此 `calls.required` 可能因没有 Trace 而失败，
`calls.forbidden` 反而可能在没有观测证据时假通过。

最小方案是 configure 时写固定的 instance Trace directory；`profile_call` 根据
`source_session_id` 使用安全派生文件名。Case 只读取自己的文件，不改 mapping。
Experiment 也读取同一 Session 文件，并把无观测证据标为 partial/unobserved，而不是
执行否定性调用断言。该方案不新增服务或全局 Runtime，也允许并发与普通请求共存。

### 8.4 `allowed_calls` 当前不是强授权隔离

当前 configure：

- 所有 Profile 的 `API_SERVER_KEY` 相同；
- 每个调用方 mapping 含全部 Agent；
- 每个 Agent 条目引用同一个 Key env；
- 同一个 Key 被写入所有 Profile `.env`。

所以 `allowed_calls` 只约束正常 `profile_call` handler。V2.1 为每个目标 Gateway
使用独立随机 Key，调用方 `.env` 只获得 self 和 allowlisted target Key，mapping
也只列 self 与 allowlisted targets。

这显著缩小正常运行凭据面，但同一 OS 用户且拥有 terminal/file 的 Agent 仍可能读取
其他 Profile 目录；因此 UI/文档必须称它为：

- machine-enforced `profile_call` Tool Policy；
- per-target credential minimization；
- **不是** OS/container/network 强隔离。

不增加 RBAC。

## 9. 状态、评测、attestation 和 release 语义

### 9.1 Case 状态

当前：

- `clean` 与 `session_only` 都只是新 Hermes Session，不能保证无 Profile Memory、
  local state 或外部系统状态；
- `retained` 是显式 caller scope；
- `initial_state` 只是追加到 instructions。

V2.1 的新写法是 `new_session`、`retained_scope`、`fresh_instance` 和
`evaluation_context`。读取旧 `clean | session_only | retained` 与
`initial_state` 时兼容迁移；新文档/UI/输出只使用真实语义。`fresh_instance`
必须由 fresh `HERMES_HOME` 或新的物理实例证据支持，不能仅靠 Session 名称。

### 9.2 configured attestation 与 live probe

当前 `attest()` 只核验 release、安装资产、mapping、configure 记录和统一模型记录，
却返回笼统 `verified: true`。它不访问 Gateway，不能证明进程在线、当前版本、
capabilities 或实际模型列表。

V2.1：

- `configured_runtime_attestation` 保留现有强文件/配置证明；
- `live_runtime_probe` 调用 `/health`、`/health/detailed`、`/v1/capabilities`、
  `/v1/models`，逐 Profile 记录可确认项；
- identity 无法由 Hermes endpoint 独立确认时标 `unverified`；
- Experiment 明确要求 configured attestation，是否还要求 live probe由证据等级
  表达，不把在线等同于配置完整。

### 9.3 evidence level

UI/API 使用有序、可缺层级：

```text
packed → installed → configured → runtime_attested
       → live_probed → cases_passed → fresh_verified
```

`packed` 只说明 Pack schema/definition snapshot；不得叫 `Validated release`。
`fresh_verified` 需要 fresh instance/HERMES_HOME 的明确运行证据，不能从普通
`cases_passed` 推断。

### 9.4 模型

当前 wrapper 用一个 model/provider/base URL 配置全部 Profile，attestation 只返回
一个 `model_fingerprint`。V2.1 保留统一默认值作为便利，但允许 Consumer 使用
Hermes 原生命令逐 Profile 覆盖；configured/live 证据逐 Profile 读取和记录实际配置。
Manifest 不加模型字段。

## 10. Dashboard 的主要 Demo 摩擦

当前四个孤立 Tabs 是 `Design / Run & Observe / Evaluate / Release`，并且：

- `Run & Observe` 永远选 `packs[0]`，不能选择 workspace；
- 用户必须手工复制 Session ID；
- Trace 标题固定为 `profile_call evidence`，不能表达非 `profile_call` 协作；
- `Evaluate` 要手工输入 runtime instance；
- `Release` 标题是 `Validated releases`；
- Design 列表存在于 overview，但 UI 只选择第一个 Design，没有清晰历史恢复入口；
- Core 首屏把 Drafter、Experiment、Release 作为并列阶段；
- 没有 Delivery 安装命令、entry HTTP、curl 示例、evidence level 或已知限制聚合页。

V2.1 改为 selected App Pack workspace：

```text
App Packs
└── <selected-pack>
    ├── Overview
    ├── Design
    ├── Sessions & Evidence
    ├── Cases
    ├── Delivery
    └── Assurance Lab
```

API 从 Pack 与 `HERMES_HOME/app-packs/*` 自动发现实例，从 entry Gateway
`/api/sessions` 自动发现最近 Sessions。无法访问时返回缺失原因，不要求用户先复制
ID。Lens 根据可见事件返回 `complete_trace | partial_trace |
unobserved_collaboration_possible`，无 Trace 不解释为无协作。Chat 继续链接 Hermes
原生 `/chat`。

## 11. Builder、Drafter、Reviewer 调整

Builder 保留原生多轮 Session，但 `PLAN_READY` 时后端同时生成：

- `PLAN.md`；
- `IMPLEMENTATION_HANDOFF.md`。

handoff 记录原始需求、对齐目标、Profile 是否必要及边界、工具/数据/权限、
Session/Memory/Skill 所有权、推荐原语、App Pack/HTTP 边界、Cases、未接入系统和
非目标。它是实现合同，不是固定 Workflow。

默认动作是 `Export handoff`；`Generate with Hermes` 是可选 Drafter。Drafter 文档
明确 `terminal.cwd` 不是安全 sandbox，输出仍需 Validator，不自动 adopt/install/
commit。

默认 Reviewer 动作是导出冻结 evidence bundle；`Review with Hermes` 可选。
Reviewer URL/Key 不再是 Core 可用性的隐性前提。

## 12. App Pack Schema Freeze

本轮不增加任何 Manifest 核心字段，不迁移 schema version，不把模型、端口、Secret、
部署或 Workflow 放入 Manifest。保留 `state_policy`、`state_compatibility`、
`allowed_calls`、`collaboration`，但文档把它们分别描述为 Pack declaration、
Validator guarantee、Consumer responsibility 和 Hermes limit。

两个反例 Pack只复用现有字段：

- Single Profile：`allowed_calls: {}`、`collaboration: []`，不注入 `profile_call`；
- Non-profile-call：使用 Hermes 原生 delegation，`collaboration` 不新增协议值，
  Case 不检查固定调用树，Lens 诚实显示 partial/unobserved evidence。

## 13. V1 compatibility 和发布包审计

当前活动 V2 CLI/Plugin/Dashboard 不导入 V1 `services/`、`store.py`、`models.py`、
旧 `cli.py` 或旧 Dashboard API/bundle。V1 仍有 8 组专用测试，并仍进入 sdist：
旧 services、脚本、scenarios、测试和历史文档都增加发布负担。

构建路径还产生不一致结果：

- `uv build` 先生成 sdist、再从 sdist 生成 wheel；该 wheel 只包含
  `plugin/profile_call` 和顶层 `plugin/__init__.py`，没有活动 `plugin/atelier`，
  但 entry point 指向 `plugin.atelier.cli_v2:main`；
- `uv build --wheel` 直接从工作树生成 wheel 时，活动 V2 与旧 `services/`、
  `store.py`、旧 CLI/API/bundle 又会全部进入。

因此“build 成功”既不证明 wheel 可用，也不证明 V1 已退出发布包。

V2.1 将：

- wheel/sdist 明确包含活动 `plugin.atelier` 与 `plugin.profile_call`；
- 明确排除 V1 `services/`、`store.py`、`models.py`、旧 CLI/API/bundle 与旧脚本；
- 删除只验证 V1 内部状态机的测试；
- 迁移文档指向 Git history/tag，而不是把 V1 runtime 继续装入 V2 包；
- 增加 wheel 内容和安装后 CLI import 回归。

V1 删除只限不活动兼容代码；V2 路径、redaction、错误类型等共享文件继续保留。

## 14. 本次保留、调整、降级、删除

| 处理 | 内容 |
| --- | --- |
| 保留 | App Pack schema v2、provenance、lock/digest、Secret/path/symlink、Candidate binding、Contract、runtime transform、update/rollback 回归 |
| 调整 | Trace client/timeout、best-effort stop、固定 Trace directory、per-target Keys/mapping、partial Lens、逐 Profile model evidence |
| 降级 | Drafter/Reviewer/Experiment/attestation/update 从默认 Core 移到 Assurance Lab；`allowed_calls` 称 Tool Policy + credential minimization |
| 兼容迁移 | Case policy 到 `new_session/retained_scope/fresh_instance`，`initial_state` 到 `evaluation_context` |
| 删除 | 递归 Workflow 关键词黑名单、仅因 Trace 的业务 delegation 禁用、Dashboard `Validated releases`、V1 发布包和内部状态机测试 |
| 冻结 | Manifest schema、update/rollback 功能扩张、可信生产发布平台方向 |

## 15. 用户级验收标准

### Core

1. 用户可以恢复历史 Design，PLAN_READY 后直接下载 PLAN + Coding Agent handoff；
2. 不配置 Drafter/Reviewer 也能完成 Design、Pack、run Lens 和 Delivery；
3. 选择一个 Pack 后能看到 Overview、Design、最近 Sessions、Cases、Delivery；
4. 已安装实例和最近 entry Sessions 自动发现，失败时显示原因；
5. Single Profile Pack 不安装 `profile_call` 仍可 HTTP 交付；
6. Non-profile-call Pack 不因 Trace 关闭 delegation，Lens 诚实显示 partial/unobserved；
7. 发布应用在 Dashboard 停止、`.atelier` 删除、工坊 Profiles 未安装时继续运行。

### 运行正确性

1. 慢/坏 Trace Sink 不显著延迟目标 dispatch，业务结果不受影响；
2. 子 Run 创建后的 timeout/cancel/SSE/network/parse 失败都会 best-effort stop；
3. stop 只按 `requested/confirmed/unknown` 报告；
4. 并发 Case 不改写共享 mapping；
5. mapping 只含 self/allowlisted targets，每目标独立 Key；
6. configured attestation 与 live probe 分离，未知明确为 `unverified`；
7. UI/API 不把 `packed` 冒充更高 evidence level。

### 回归和交付

1. Mini VOC、Project Defense、Single Profile、Non-profile-call 四个 Pack
   validate/install/start/HTTP smoke；
2. 两个现有应用的独立交付、update/rollback 负向行为不回归；
3. 每 Profile 可由 Hermes 原生配置不同模型，证据逐 Profile 展示；
4. 全量 pytest、Ruff、Dashboard JS、build、wheel contents、diff check、Secret scan；
5. 浏览器完成 selected-pack workspace、Design 恢复、instance/Session 自动发现、
   partial trace、evidence level 和 Core/Lab 分区，console 无错误。

## 16. 实施边界

实现顺序以运行正确性优先，然后是 Agent 自主性、核心体验、语义清理和去制度化。
不新增 Runtime、消息队列、后台服务、RBAC、Workflow、Fixture DSL、Schema V3 或部署
平台。每个高风险改动必须先有能失败的确定性回归，真实 Hermes smoke 只证明本次链路，
不把随机模型输出升级为产品保证。
