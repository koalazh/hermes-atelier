# Hermes Atelier V2 Coding Agent 工作指南

## 适用范围与规则优先级

本文件适用于整个仓库。用户当前任务和更高优先级指令始终优先；本文件固化长期架构约束，不把某个一次性流程强制成所有任务的步骤。

开始修改前按任务读取：

- 产品定位与 Kill/Pivot 条件：[`docs/PROJECT.md`](docs/PROJECT.md)；
- 组件与所有权：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)；
- App Pack、协作、评测与发布：[`docs/APP_PACK.md`](docs/APP_PACK.md)、[`docs/PROFILE_CALL.md`](docs/PROFILE_CALL.md)、[`docs/CASES_AND_EXPERIMENTS.md`](docs/CASES_AND_EXPERIMENTS.md)、[`docs/RELEASE.md`](docs/RELEASE.md)；
- 安全、迁移与验证：[`docs/SECURITY.md`](docs/SECURITY.md)、[`docs/MIGRATION_FROM_V1.md`](docs/MIGRATION_FROM_V1.md)、[`docs/VALIDATION.md`](docs/VALIDATION.md)。

设计文档说明产品边界；精确接口和错误形状以当前代码、测试和 Hermes 实际能力为准。发现冲突时先定位差异，不得修改 Hermes 核心掩盖问题。

## 修改前必须完成

1. 运行 `git status --short`，保留用户已有改动。
2. 阅读直接相关实现、测试和设计文档，不根据 V1 记忆修改。
3. Bugfix 先复现并建立 producer → protocol → consumer 调用链，再写最小回归。
4. 明确可验证成功标准；只有缺失信息会改变目标、权限或安全边界时才询问用户。
5. 每条改动都必须追溯到当前需求，不顺便重构或加入推测性扩展。

## 不可破坏的 V2 架构不变量

- Hermes 拥有 Profile、Gateway、Session、Run、Memory、Plugin、模型、工具和进程生命周期。
- Atelier 是可删除的开发工坊，只拥有 Design 证据、Trace 索引、Case/Experiment 和 Release 验证；删除 Studio 或 `.atelier` 不得改变已发布应用的行为。
- 不得在 Atelier 核心编码业务流程、路由、重试、fan-out、aggregate、judge 或固定 Agent 拓扑。
- App Pack 使用逻辑 Agent ID；安装时才由 Consumer 选择实例名并映射为物理 Profile。
- `allowed_calls` 是权限边界，不是路由图。何时调用、调用谁、顺序、充分性和结果组合由入口 Agent 决定。
- `profile_call` 是可选、独立于 Atelier 的应用 Plugin；它只解析逻辑目标、鉴权、调用目标 Hermes Run 并返回真实元数据。
- 通用对话直接使用 Hermes 原生 Session/Chat/Run。Atelier 不包装第二套通用 Runtime、Session、Endpoint Registry、PID Registry 或健康状态机。
- Case 描述输入、状态、Memory Policy、通用结果断言和人工评审提示，禁止描述 Workflow。
- Experiment 冻结 App/Definition/Model/Case/Memory 条件并保存真实 Trial；Reviewer 只分析整个 Experiment，不能改应用或宣称一次结果已经完成优化。
- Builder 规划 Profile 默认无文件、终端和代码执行权限；只有显式 `Generate Draft` 才调用独立、写范围受限的 Drafter Profile。Draft 不等于采纳、安装、提交或批准。
- 候选修改通过 Git branch/worktree、Diff 和 Experiment 管理，不对当前工作树执行隐式 Patch。
- Hermes 原生补齐等价能力后，优先删除 Atelier 重复代码。

## 目录职责

| 路径 | 职责与限制 |
| --- | --- |
| `plugin/atelier/` | 业务无关的 V2 Design、Trace 索引、Experiment、Release、CLI 和 Dashboard 扩展；不得增加应用特判或运行监管。 |
| `plugin/profile_call/` | 可随 App Pack 发布的独立协作 Plugin；不得导入 Atelier 或依赖 `.atelier`。 |
| `profiles/atelier-builder/` | 只读多轮规划 Profile。 |
| `profiles/atelier-drafter/` | 显式 Draft 的受限写 Profile。 |
| `profiles/atelier-reviewer/` | 独立只读 Experiment Reviewer。 |
| `apps/<app-id>/` | V2 `app.yaml`、Profile Distributions、业务 Plugins、Cases、Contracts 和接收方文档。 |
| `tests/` | 确定性行为、fake-Hermes 集成、发布、生命周期和文档回归。 |
| `.atelier/v2/` | 可删除的本地开发证据，禁止提交或作为应用运行事实源。 |
| Consumer `HERMES_HOME` | Hermes 拥有的 Profile、`.env`、Memory、Sessions、日志、PID 和 `local/app-runtime.json`。 |

迁移期 V1 模块仅用于回归证据，不得被 V2 `plugin.yaml`、CLI 或 Dashboard 活动入口重新引用。

## Hermes 集成规则

- 不修改 Hermes 核心源码。最低兼容版本是 0.19.0，但版本字符串不能替代真实能力探针。
- 所有 Profile 操作显式使用 `hermes -p <profile>`，不依赖 sticky active Profile。
- Pack wrapper 只能代理原生 install/config/gateway/update，并生成无 Secret 的逻辑映射；不得维护 PID、后台 supervisor、Endpoint DB 或第二个状态机。
- 当前 Hermes multiplex 的 Plugin Manager 是进程级单例，不能隔离不同 Profile 的业务 Plugins；在该能力变化前，每个物理 Profile 使用独立 loopback Gateway。
- HTTP 层只允许有限的连接/读取重试，不得自动选择备用专家或实现业务重试。
- Dashboard 使用 Hermes Plugin SDK，不复制 Profile、Chat、Session、模型、密钥、日志或 Gateway 管理界面。

## App Pack 与业务资产

`app.yaml` 只描述 `schema_version: 2`、Pack 身份与版本、逻辑 Agents、唯一公开入口、`allowed_calls`、协作原语、公开 OpenAI 接口、状态策略、Cases、Contracts 和说明。

禁止加入 `steps`、`workflow`、`if`、`else`、`route_when`、`parallel`、`fan_out`、`aggregate`、`judge` 或业务重试策略。业务差异必须留在应用 SOUL、Skills 和工具中。

发布物不得包含 `.env`、密钥、Memory、Sessions、Trace、PID、`local/`、Atelier DB 或主工程运行态。示例只能显式 validate/release/install，不得在默认安装时启动。

## 安全与失败语义

- 真实密钥只能进入 Consumer 拥有、权限为 `0600` 的 Profile `.env` 或进程环境；不得进入源码、fixture、日志、Trace、`app.lock`、文档或 Git。
- 所有 Gateway 默认只绑定 `127.0.0.1`；只有唯一入口端口可由 Consumer 选择加入 ingress。
- 逻辑映射只保存 API Key 环境变量名，不保存 Secret；内部 Profile 端口也必须认证。
- 所有 Pack、Draft、Case、Distribution 和候选路径必须解析在声明根目录内，拒绝绝对路径、`..`、symlink 越界和敏感运行态。
- `profile_call` 在 dispatch 前无法解析或授权时失败关闭；dispatch 后 Trace Sink 失败时保留真实结果并标记 `trace_degraded`。
- Draft、Release 或 update 部分失败必须明确报告；update 的 smoke 失败执行 best-effort 回滚，不得伪造原子性或成功。
- `state_compatibility` 只能提示 `preserve | review_required | reset_recommended`，wrapper 不得静默删除 Memory 或 Sessions。

## 开发与验证

修改应小而可证：先写或更新回归，再实现最小行为，随后运行风险相称的门禁。

| 改动类型 | 最低验证 |
| --- | --- |
| Python 逻辑 | 相关 `uv run pytest -q tests/<file>.py`，再 `uv run ruff check .` |
| App Pack/release/update | 对应测试、两示例 validate/release；生命周期变化需要 fresh `HERMES_HOME` smoke |
| Session/Trace/Experiment | fake-Hermes 回归；协议变化需要真实 Hermes smoke |
| Dashboard/API | API 测试、`node --check plugin/atelier/dashboard/dist/index_v2.js`；视觉变化需真实浏览器检查 |
| 全局、依赖或发布资产 | `uv run pytest -q`、`uv run ruff check .`、`uv build` |
| 文档 | `uv run pytest -q tests/test_documentation.py` 与链接检查 |

真实模型 smoke 只证明链路可执行，不证明生产质量、性能或业务正确率。任务启动的 Gateway、进程和临时运行态必须在验证后停止和清理。

## 文档与 Git

- 面向人的 README、`AGENTS.md` 和 `docs/**/*.md` 使用中文说明；协议、schema、状态、命令和代码标识可保留英文。
- 精确区分 deterministic test、真实 smoke、历史证据、推断和未知。
- 除 `docs/VALIDATION.md` 外，不在长期设计文档写快速过时的测试数量、Run ID、commit hash、机器绝对路径或一次性状态。
- 不提交 `.hermes-runtime/`、`.atelier/`、`apps/.drafts/`、Secret、Memory、Sessions、日志或真实 Trace。
- 未经明确要求不 push、不公共发布、不部署、不创建 PR。
- 交付前运行 `git diff --check`、全量门禁和密钥扫描，并说明验证证据、已知边界与进程清理结果。

## 完成标准

只有请求行为真实存在、关键失败路径有证据、架构与安全边界未破坏、文档与代码一致、工作树与 Secret 检查干净，且剩余限制被如实披露时，才报告完成。
