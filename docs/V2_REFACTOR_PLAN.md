# Hermes Atelier V2 源码审计与重构计划

## 1. 审计结论

Atelier V1 不是低质量实现；它完整实现并验证了旧合同。但旧合同把当时缺失或未验证的能力固化成 Atelier 运行协议，造成了错误的状态所有权：应用调用必须先有 Atelier Run，跨 Profile 调用必须解析 Atelier Session，Endpoint、端口、PID、Gateway 和统一模型配置由 SQLite 与 `ProfileService` 管理，Dashboard 进程还承担 Build、Run、Review 和 Proposal 后台任务。

V2 不应在 V1 上继续增加状态机。收敛方向是：

```text
对话形成设计  →  Hermes 原生 Session 运行  →  Atelier 可选观察
      ↓                                      ↓
批准后生成 Draft                         Cases / Experiments
      ↓                                      ↓
Git 候选变更                             App Pack Release
```

发布后的业务链路必须是：

```text
外部客户端
  → Hermes 原生 HTTP API
  → 入口 Profile
  → 独立 profile_call 或其他业务自选协作原语
  → 内部 Profile
```

这条链路不读取 Atelier SQLite，不要求 Builder/Reviewer/Dashboard，不解析 Atelier Session ID，也不由 Atelier 启停 Gateway。

## 2. 审计范围与基线

审计对象包括：

- `plugin/atelier/`、Dashboard Plugin、SQLite schema；
- `BuildService`、`RunService`、`ReviewService`、`ProposalService`、`ProfileService`；
- Mini VOC、Project Defense、Builder 与 Reviewer Profile；
- 全部自动化测试、V1 验证记录和当前项目本地运行态；
- 当前安装的 Hermes Agent 0.19.0（2026-07-20，upstream `9eb7b1a6`）源码、CLI 与真实接口。

开始时仓库 `main` 干净，HEAD 为 `117f4d2`。未修改基线通过：

- 完整 pytest 回归；
- Ruff；
- Dashboard JavaScript 语法检查；
- sdist/wheel 构建；
- 现有 capability probe，9 个 V1 Profile 均健康。

本轮还真实执行了：

- Mini VOC `cross-domain`：入口完成，产生 Product 与 Transaction 两个真实 child Hermes Run；
- Project Defense `evidence-gap`：入口完成，产生 Source child Hermes Run，并明确拒绝没有项目证据的 p99 改善数字。

这些 smoke 只证明 V1 链路和业务边界可执行，不证明模型输出质量，也不证明 V2 独立发布条件。

## 3. V1 当前真实架构

### 3.1 版本化资产

```text
apps/<app-id>/
├── app.yaml                    物理 Profile 名与 allowed_calls
├── profiles/<role>/            Hermes Distribution
└── scenarios/                  V1 单次 Run 输入

profiles/atelier-builder/       Builder Distribution
profiles/atelier-reviewer/      Reviewer Distribution
plugin/atelier/                 工具、Store、服务、CLI、Dashboard
```

### 3.2 运行态

```text
.hermes-runtime/profiles/*      Hermes Profile、Session、Memory、配置与密钥
.atelier/atelier.db             App、Endpoint、Run、Span、Event、Build、Review、Proposal
.atelier/logs/*                 Atelier 启动的 Gateway 日志
apps/.drafts/*                  Build 与 Proposal 草稿
```

### 3.3 核心调用链

1. `bootstrap.py` 注册所有示例，安装 Builder、Reviewer 与全部业务 Profiles。
2. `ProfileService` 分配端口、生成 API Key、覆盖模型配置、写 `.env`、记录 Endpoint。
3. `RunService.start_root` 先写 Atelier Run，并生成 `at_<run>_root` Session。
4. 入口 Agent 调用 `atelier_call`。
5. Plugin 要求 Hermes handler 的 `task_id == session_id`，解析 Session 得到 Atelier Run/Span。
6. `RunService.call` 查 SQLite 中的 App 与 allowed calls，经 Endpoint Registry 调用目标 Profile，生成 child Session 与 Span。
7. Dashboard/Review 再从 SQLite 和 Hermes Session 拼装 Trace Bundle。

因此 Dashboard 进程可以停止，但 `.atelier` 与 Atelier Plugin 不能从业务调用链移除。V1 的“Dashboard 非 Runtime”只覆盖进程，不覆盖协议与状态依赖。

## 4. 用户实际体验路径

### Build

用户提交一次请求后，Dashboard 立即创建后台 `asyncio.Task`；Builder 在一个 Hermes Run 内同时对齐、设计并生成完整应用，最后进入批准。用户没有真正的多轮调查 Session，也无法在生成前逐轮修改目标。

### Playground

用户只能创建一次性 Atelier Run。Hermes 原生 Session/Chat 虽已存在，但 V1 重新包了一层 Run，跨轮继续、补充和纠正不是主体验。

### Observe

Trace 来自真实 Hermes Runs/SSE 和真实 `atelier_call`，这一点应保留；但 Trace 的授权与调用成功共享同一个 SQLite 前置条件，观测故障会阻止业务。

### Review / Proposal / Replay

Reviewer 读取冻结 Bundle，Builder 生成 Patch，后端对当前工作树执行 `git apply`。Replay 复用原 `memory_scope`，没有明确的 clean/session-only/retained 评测语义；Review Bundle 中的应用定义可能是 Review 时的当前目录，而不是执行时定义。

## 5. Atelier 当前承担的 Runtime 职责

以下职责直接由当前源码确认：

| V1 职责 | 当前实现 | 问题 |
| --- | --- | --- |
| Profile 安装/更新 | `ProfileService.install_distribution` | 重复 Hermes Distribution CLI，并与 Atelier App 注册耦合 |
| 模型与密钥配置 | `configure_runtime` / `_set_model_config` | 把所有 Profiles 绑定到统一 Provider 与 Atelier 环境变量 |
| 端口和 Endpoint | `profile_endpoints`、端口扫描 | 自建运行事实源 |
| PID 与 Gateway | `start/stop/restart`、PID 所有权与日志 | 重复 Hermes 原生 Gateway 生命周期 |
| Session 协议 | `at_<run>_root`、`at_<run>_<span>` | 普通 Hermes Session 无法调用专家 |
| 跨 Profile 调用 | `atelier_call` + SQLite Run/Span | Atelier DB 成为正确性依赖 |
| 通用 Run/Chat | `RunService` 与 Playground | 弱化重做 Hermes Sessions/Chat/Runs |
| Builder 后台任务 | Dashboard 进程内 `asyncio.Task` | 隐藏生命周期，重启后难恢复 |
| Proposal 版本控制 | Patch Store + `git apply/-R` | 平行且不完整地重做 Git |

## 6. 与 Hermes 0.19.0 原生能力的重叠

当前 Hermes 源码与 CLI 已确认：

- Profile Distribution 原生 `install/update/delete/info`；update 保留 `.env`、Memory、Sessions、workspace 与 `local/`；
- Gateway 原生 `run/start/stop/restart/status/list/install/uninstall`；
- `/api/sessions` 提供 create/get/patch/delete/messages/fork/chat/chat-stream；
- `/v1/chat/completions` 支持 `X-Hermes-Session-Id` 与 `X-Hermes-Session-Key`；
- `/v1/responses` 支持 `previous_response_id`；
- `/v1/runs` 提供异步执行、SSE events、status、approval 与 stop；
- `gateway.multiplex_profiles` 可路由多个 Profile 的模型、Secrets 与 Session，但 Hermes 0.19.0 的 Plugin Manager 是进程级单例，只在 Gateway 默认 Profile 下发现一次插件；因此它不适合需要不同业务 Plugins 的当前两个示例；
- Profile 路由、Plugins、Dashboard Plugin 与 Kanban 已由 Hermes 提供。

V2 应直接采用这些接口。Atelier 不再维护 Profile Manager、Endpoint Registry、PID Manager、端口扫描、Session Store、通用 Chat 或 Gateway 状态机。

## 7. 保留、重写与删除

### 保留

- Hermes Atelier 名称和 Hermes Dashboard Plugin 入口；
- Builder、Reviewer 作为完整 Hermes Profiles；
- Mini VOC 与 Project Defense 的业务 SOUL、Skills、工具和真实 smoke 经验；
- 默认单 Agent、基于现实边界拆 Profile 的原则；
- allowed calls 作为权限边界；
- 真实 Tool Call / Session / Run 元数据、脱敏、路径限制和明确批准；
- 项目本地 HERMES_HOME 作为开发与测试隔离方式，但不作为发布要求。

### 重写

- `app.yaml`：使用逻辑 Agent ID，物理名只在安装时生成；增加 Public HTTP、State Policy、Cases 与 Contracts 等稳定事实，不加入流程；
- `atelier_call`：替换为独立 `profile_call` Plugin；无 Atelier Trace Context 时照常调用，有可选 Trace Sink 时只做 best-effort 观测；
- Builder：Hermes 原生多轮 Session，先维护 `PLAN.md`，只有明确生成动作才创建 Draft；
- Run：直接复用 Hermes Session/Chat/Responses/Runs；Atelier 只提供当前轮 Trace 与 Case/版本关联；
- Scenario/Replay：替换为 Case、Experiment、Trial、显式 Memory Policy 与 Definition Snapshot；
- Review：分析完整 Experiment，只输出诊断、假设、不确定性和验证建议；
- Release：把 App Pack 校验、lock、fresh install 与独立 HTTP smoke 变成一等能力；
- Update：薄代理 Hermes stop/update/start，保留用户状态，并在失败时诚实报告或 best-effort rollback。

### 删除或停用

- `profile_endpoints` 作为运行事实源、端口扫描、PID 和自管 Gateway 日志；
- Atelier 专属 Session 解析与 `task_id == session_id` 协议；
- 所有业务 Profile 强制安装 Atelier Plugin；
- Dashboard 的 Profile start/stop/restart 与通用 Run 包装；
- 一次性后台 Build、旧 Playground、固定 Review → Patch → Replay 状态机；
- 对当前用户工作树直接 `git apply` 的 Proposal 中心；
- bootstrap 默认安装 Builder、Reviewer 和全部示例；
- 统一模型配置覆盖。

V1 数据表可只读迁移或保留在旧数据库中，但 V2 代码不再把它们作为运行事实。迁移完成后不为旧协议继续维护新写路径。

## 8. V2 收敛设计

### 8.1 Hermes App Pack

Pack 是普通目录或 Git 仓库。`app.yaml` 保存稳定事实；`app.lock` 保存内容摘要、精确 Distribution 与 commit/tag；`local/`、`.env`、Memory、Sessions、Trace 和任何 Atelier 数据都不进入发布物。

安装器把逻辑 ID 物化为 `<instance>--<agent>`。运行映射写入每个调用方 Profile 的用户保留目录 `local/app-runtime.json`，不写回源码。映射只描述物理 Profile、Hermes HTTP URL 和读取密钥的环境变量名，不保存 Secret。

### 8.2 原生 Gateway 与公开入口

V2 默认使用 Hermes 原生的一 Profile 一 Gateway 模式，为每个物理 Profile 分配显式本地端口。`./app start/stop/status` 只逐个代理 Hermes 原生命令；PID、launchd 服务、健康状态与 Session 仍完全由 Hermes 管理。`INSTALL.md` 同时给出不使用 wrapper 的等价命令。

真实 capability probe 已验证：multiplex 能正确切换请求 Profile，却不会重新发现路由 Profile 私有的 `profile_call` 和业务 Plugins，入口因此看不到这些工具。把所有插件提升为进程全局会破坏工具隔离，所以不采用。未来 Hermes 若支持 Profile-scoped Plugin registry，Pack 可重新合并监听端口，而无需改变逻辑 Agent 或 `profile_call` 协议。

Atelier 不拥有 Gateway 状态。内部 Profiles 不在 Public Contract 中暴露；真实生产 ingress、认证和网络隔离仍由 Consumer 负责。

### 8.3 独立 profile_call

`profile_call` 随需要调用专家的业务 Profile Distribution 发布，不导入 `plugin.atelier`，也不读取 `.atelier`。它：

1. 从当前 Profile 的 `local/app-runtime.json` 解析逻辑目标；
2. 校验 `allowed_calls`；
3. 调用目标 Hermes `/v1/runs`，消费真实 SSE 并返回结果、Session/Run 元数据；
4. 仅在存在可选 Trace Context/Sink 时发送真实调用事件；Trace 失败不改变业务结果。

它不选择专家、顺序、并行、聚合、业务重试、降级或 Workflow，也不是唯一允许的协作原语。

### 8.4 Design / Run / Observe

Dashboard 只做开发体验：

- Design 绑定一个 Hermes Builder Session，多轮消息持续更新 `PLAN.md`；
- `Generate Draft` 是独立明确动作，后端才提供 Draft 写目录；`Adopt` 再由 Git/文件操作显式执行；
- Run 直接绑定入口 Hermes Session，每轮保存返回的 Session/Response/Run ID；
- Observe 只索引 `profile_call` 发出的真实事件和 Hermes 元数据，不从自然语言猜调用关系。

不在 Dashboard 进程创建无法恢复的隐藏 Runtime 任务；异步状态以 Hermes Run 或显式磁盘记录为准。

### 8.5 Case / Experiment

Case 只包含输入、初始状态、`clean | session_only | retained`、少量通用 assertions 与人工评价提示，不描述工作流。应用可提供自有 Evaluator。

Experiment 在开始时冻结：Pack revision、全部 Profile 定义/SOUL/Skills/Plugins 摘要、模型与 Provider 指纹、Case、Memory Policy。Trial 引用真实 Hermes Session/Run/Response 与 Trace。Case 目录不可被候选分支当作“优化”修改；同时改 Case 与 Profile 必须被标记为不同实验条件。

### 8.6 候选修改

Atelier 只展示 Candidate branch/worktree、Diff 与 Experiment 比较。创建、合并、cherry-pick 或拒绝由 Git/Coding Agent 原语完成，不再维护 Patch 数据库或直接修改当前工作树。

## 9. 编码前必须真实验证的 Hermes 能力

源码与 Hermes 自身测试已证明接口存在，V2 完成前仍必须在 fresh HERMES_HOME 验证：

1. 本地 Distribution 安装、物理重命名、update 与 delete；
2. 每个物理 Profile 的原生 Gateway 对 Models、Chat、Responses、Runs、Sessions 与私有 Plugins 的隔离；
3. Profile 内独立 Plugin 能读取当前 Profile 的 `local/`；
4. `profile_call` 在无 Atelier、无 `.atelier`、普通 HTTP Session 下调用专家；
5. Hermes update 保留 `.env`、Memory、Sessions 与 `local/`；
6. Gateway stop/start/status 的平台行为和失败状态；
7. Builder 原生 Session 多轮继续与 Draft 权限切换；
8. 模型/Provider 指纹可从当前 Profile 配置与运行响应稳定采集。

能力失败时优先调整 App Pack 或公开限制，不修改 Hermes 核心，也不重建平行 Runtime。

## 10. V2 最小垂直闭环

最先实现和保持可运行的闭环是：

1. 将 Mini VOC 转成逻辑 Agent App Pack；
2. fresh HERMES_HOME 安装为一个实例；
3. 入口 Profile 使用独立 `profile_call`；
4. 为每个物理 Profile 启动 Hermes 原生 Gateway；
5. 从外部客户端调用入口原生 HTTP API；
6. 在没有 Dashboard 和 `.atelier` 的条件下完成专家调用；
7. 用 clean Case 记录 Definition Snapshot、Trial、Trace 与 assertions；
8. 生成可校验 `app.lock` 与 Release 目录。

这条闭环成立后，再迁移 Project Defense、多轮 Builder/Run、Reviewer 与 update。不能先建完整平台再寻找运行证据。

## 11. 迁移风险与回退

| 风险 | 控制与回退 |
| --- | --- |
| Hermes multiplex 无法隔离 Profile 私有 Plugins | 已选择多个 Hermes 原生 Gateway；wrapper 只代理生命周期并生成静态端口映射，不恢复 Atelier PID/Endpoint Registry |
| 逻辑/物理 Profile 映射错误 | install preflight 校验全部 Agent 与 allowed calls；映射只在成功后原子替换；失败保留旧 `local/` |
| update 删除 Profile 后留存运行态 | 先 stop，使用 Hermes `profile delete` 清理旧物理 Profile，再生成映射；失败不报告成功 |
| update/rollback 造成源码与运行态不一致 | release 以不可变 Pack revision 和 lock 为输入；失败时按旧 lock 重新 `profile update/install`，并执行 smoke Case |
| Memory 污染实验 | 默认 `clean` 使用隔离 HERMES_HOME/Session；`retained` 必须显式选择并记录 |
| V1 历史数据不可读 | 保留迁移文档和只读导出路径；V2 不继续写 V1 Runtime 表 |
| 直接删除 V1 测试掩盖回归 | 保留测试文件或用户级行为覆盖；废弃断言在迁移文档逐项说明替代证据 |
| 大规模重写失去可回退点 | 本地提交按审计、Runtime 解耦、Design/Run、Experiment、Release、示例迁移和删除旧设施分组；任何阶段可回退到前一可运行提交 |

## 12. 实施与验证顺序

1. 先提交本审计与 V2 合同。
2. 实现独立 `profile_call`、逻辑 Agent schema、runtime mapping 与 Studio-off 单测/真实 smoke。
3. 将 Builder/Run 改为 Hermes 原生多轮 Session，加入明确 Draft 授权和每轮 Trace。
4. 实现 Case/Experiment/Definition Snapshot/Memory Policy 与 Reviewer 实验分析。
5. 实现 Pack validator、lock、release、fresh install、update/rollback 和示例客户端。
6. 迁移两个示例，验证不同协作与 Memory 行为，且不默认安装。
7. 删除不再使用的 Endpoint/PID/Gateway/Proposal/旧 Session 协议与对应 UI；更新全部文档和 ADR。
8. 执行完整 deterministic 回归、build、密钥扫描、fresh-install、Studio-off、`.atelier`-off、update/rollback、两个真实 smoke 和隔离 Completion Challenge。

## 13. 决策自检

新增模块、字段或状态前必须能说明：它是否只服务 Design/Observe/Evaluate/Package/Release，为什么 Hermes/Profile/Skill/Plugin/普通 Git 不能承担，以及删除它是否只损失开发便利而不损失发布应用正确性。不能说明时不实现。

V2 的目标不是把七阶段 V1 流程做得更完整，而是让以下所有权在源码和运行证据中同时成立：

> Design through conversation.
> Run through Hermes.
> Observe through Atelier.
> Evaluate through cases.
> Change through Git.
> Deliver through App Packs.
