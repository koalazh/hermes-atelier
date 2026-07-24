# Hermes Atelier Coding Agent 工作指南

## 适用范围与规则优先级

本文件适用于整个仓库，指导后续 Coding Agent 进行功能开发、Bugfix、重构、测试和文档维护。

用户当前任务和更高优先级指令始终优先。本文件负责固化仓库的长期工程约束，不替代具体需求，也不把 task-loop 等流程作为每个任务的固定步骤。上级指令、用户明确调用或已安装 Skill 的触发规则要求使用某项流程时，应按对应 Skill 执行。

开始工作前按用途读取以下资料：

- 产品定位、非目标和 Kill/Pivot 条件：[`docs/PROJECT.md`](docs/PROJECT.md)；
- 架构不变量和组件边界：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)；
- Builder、Reviewer 与批准语义：[`docs/BUILDER.md`](docs/BUILDER.md)；
- Session、Run、Span 和事件关联：[`docs/TRACE_MODEL.md`](docs/TRACE_MODEL.md)；
- 密钥、路径、进程和网络边界：[`docs/SECURITY.md`](docs/SECURITY.md)；
- 当前可复现命令和已知限制：[`README.md`](README.md) 与 [`docs/VALIDATION.md`](docs/VALIDATION.md)。

产品边界以设计文档为准；精确接口、错误形状和当前行为以代码、测试以及当前 Hermes 实际能力为准。两者冲突时不要静默选择：先定位差异；Hermes 接口变化应优先调整 Atelier 与文档，不得通过修改 Hermes 核心掩盖。

## 修改前必须完成

1. 运行 `git status --short`，识别并保留用户已有改动；不要覆盖、回退或格式化无关文件。
2. 阅读与任务直接相关的实现、测试和上述设计文档；不要只根据文件名或旧结论修改。
3. Bugfix 先复现并建立调用链，区分根因、直接失败点和协议/输入诱因，再决定是否修改。
4. 明确最小成功标准及验证方式。普通技术取舍由 Agent 自主完成；只有缺失信息会实质改变目标、权限、安全或兼容边界时才询问用户。
5. 检查是否存在更简单的实现。每条改动都应能追溯到当前需求，不提前增加“以后可能需要”的扩展点。

## 不可破坏的架构不变量

- Hermes Agent 自主负责业务理解、任务拆解、专家选择、调用顺序、工具使用、证据判断和结果汇总。
- 不得在 Atelier 核心编码业务流程、业务路由、业务重试、fan-out、aggregate、judge 或固定 Agent 拓扑。
- Atelier 只控制现实边界：Profile 身份、应用归属、`allowed_calls`、Endpoint、凭据、Session/Run 关联、Trace、文件范围、批准和进程健康。
- `atelier_call` 是唯一受 Atelier 观测的跨 Profile 调用边界。它不负责选择专家、规划步骤或解释业务结果。
- Atelier Run 只关联多个 Profile-local Hermes Sessions/Runs，绝不替代或合并它们。
- `.atelier/atelier.db` 是唯一 Atelier 状态事实源；不得增加后台 JSONL 镜像或第二个权威 Store。
- Builder 只能写 `apps/.drafts/<build-id>/`；Reviewer 只读冻结 Trace Bundle；候选 Patch 只有后端明确批准后才能应用。
- Dashboard 只是 Hermes Dashboard Plugin Tab，不是独立平台或常驻 Runtime；不得复制 Hermes 已有的 Profile、Config、密钥、Skill、MCP、Session、Chat、日志或 Gateway 管理页面。
- Hermes 原生补齐可靠等价能力后，优先删除 Atelier 重复代码，而不是维护兼容层。

## 目录职责

| 路径 | 职责与限制 |
| --- | --- |
| `plugin/atelier/` | 业务无关的 Plugin、SQLite Store、Hermes HTTP 边界、服务、CLI 和 Dashboard 扩展。禁止加入 Mini VOC、Project Defense 或其他应用特判。 |
| `profiles/atelier-builder/` | Builder Profile Distribution、SOUL 和薄 Builder Skill。不得固化 Agent 数量、角色模板或业务流程。 |
| `profiles/atelier-reviewer/` | 独立只读 Reviewer。不得直接修改应用、Memory、场景或评价标准。 |
| `apps/<app-id>/` | 业务专属 `app.yaml`、Profiles、SOUL、Skills、工具和场景。新增专家或业务路由变化应尽量只修改当前应用。 |
| `scripts/` | 项目本地 bootstrap、启停、状态、能力探针和 smoke；所有路径必须解析到当前仓库。 |
| `tests/` | 单元、fake-Hermes 集成、完整闭环、文档和生命周期回归。测试必须验证行为，不把实现细节数量当作业务指标。 |
| `docs/`、`README.md` | 面向用户和开发者的中文文档。协议名、字段名、状态码和命令可保留英文。 |
| `.hermes-runtime/`、`.atelier/`、`apps/.drafts/` | 仅本地运行态，禁止提交、复制密钥或作为源码修改目标。 |

## Hermes 集成规则

- 默认 `HERMES_HOME` 必须是当前仓库绝对路径下的 `.hermes-runtime`；所有具体 Hermes 命令显式使用 `-p <profile>`，不得依赖 sticky active Profile。
- Profile 安装和更新使用 Hermes 原生 Distribution 命令，保留 Hermes 管理的 Memory、Sessions、凭据、日志和其他运行数据。
- 不修改 Hermes 核心源码。当前最低兼容版本是 0.19.0，但版本字符串不能替代 `scripts/capability_test.py` 的能力验证。
- V1 保持每 Profile 独立 Gateway/API Server，只绑定 `127.0.0.1`；不得顺手引入 multiplex Gateway。
- Plugin handler 必须从 Hermes context 获得来源 Profile、`task_id` 和 `session_id`。上下文缺失或不匹配时返回 `incompatible_hermes`，不得从自然语言猜测身份。
- Root Session 使用 `at_<run-id>_root`，child Session 使用 `at_<run-id>_<span-id>`；长期 Memory scope 通过 `X-Hermes-Session-Key` 独立传递。
- Dashboard bundle 使用 `window.__HERMES_PLUGIN_SDK__` 提供的 React、组件和 API client；不得打包自己的 React。
- HTTP 层只允许有限、幂等的连接或读取重试；不得自动选择备用专家或实现业务级重试。

## app.yaml 与业务资产

`app.yaml` 只允许描述应用 ID、显示名称、入口 Profile、Profiles、Distribution source、`allowed_calls`、场景目录和可选描述。

禁止加入 `steps`、`workflow`、`if`、`else`、`route_when`、`parallel`、`fan_out`、`aggregate`、`judge` 或业务重试策略。`allowed_calls` 是安全白名单，不是业务路由图。

业务差异必须留在应用的 SOUL、Skills 和工具中。只有两个以上不同应用都明确需要的业务无关机制，才考虑进入 Atelier 核心。

## 安全与失败语义

- 真实密钥只能写入被忽略、权限为 `0600` 的运行态 Profile `.env`；不得进入源码、测试 fixture、日志、Trace Bundle、SQLite、浏览器响应、文档或 Git 历史。
- Dashboard 和 Profile API 只允许 loopback。不要提供公网部署说明，也不要允许 `0.0.0.0`。
- 浏览器不得直接调用业务 Profile，API Key 只能由后端读取。事件、错误、反馈和导出必须经过脱敏。
- 所有 draft、scenario、Profile source、Trace Bundle 和 Patch 路径必须解析并校验在声明根目录内；拒绝 symlink、`..`、绝对越界路径和密钥文件。
- Proposal 只能修改当前 `apps/<app-id>/`，必须完整展示 Diff、dry-run 并等待明确批准。
- Profile PID 在采纳、显示或终止前必须验证属于目标 `hermes -p <profile> gateway run`，不得仅凭 `kill(pid, 0)` 判断所有权。
- Trace 失败不得返回伪造成功。dispatch 前无法可靠授权或建立关联时失败关闭；dispatch 后事件落盘失败时返回真实结果并标记 `trace_degraded`。
- `stopping` 只表示 stop 请求已发送；没有 terminal event/status 时不得报告已经 `cancelled`。
- 启动、Build 或 Proposal 部分失败时必须清理或回滚已产生状态；无法完整清理时保留可管理状态并明确报告，不得留下 Atelier 不知道的孤儿进程。

## 开发与 Bugfix 流程

### Bugfix

1. 用现有测试、最小输入、fake Hermes 或真实能力探针复现；
2. 追踪 producer → protocol/API → consumer → Store/UI 的真实调用链；
3. 写出可证伪根因假设，必要时增加最小观测；
4. 先增加会失败的回归测试，再实施最小修复；
5. 运行相关测试和风险相称的完整回归，记录未验证边界。

不要顺便重构相邻代码、清理已有 dead code、重排无关格式或修改未被当前问题触发的行为。

### 功能开发

1. 确认功能属于 Atelier 稳定边界还是某个应用；
2. 若可只修改 `apps/<app-id>/`，不要改 Plugin 核心；
3. 优先复用 Hermes 原生能力，不建立平行 Runtime/Registry/Session/Memory 抽象；
4. 先定义可运行验收场景和失败语义，再实现最小代码；
5. 同步必要测试和中文文档，不加入推测性配置项或扩展接口。

## 验证矩阵

按改动风险选择验证，不能用较低层检查冒充更高层证据：

| 改动类型 | 最低验证 |
| --- | --- |
| Python 逻辑或 Store | 相关 `uv run pytest -q tests/<file>.py`，然后 `uv run ruff check .` |
| Run/Span/Review/Proposal 生命周期 | 相关测试加 `uv run pytest -q tests/test_full_workflow.py` |
| 全局行为、依赖或发布资产 | `uv run pytest -q`、`uv run ruff check .`、`uv build` |
| Dashboard bundle/API | 相关 API 测试、`node --check plugin/atelier/dashboard/dist/index.js`；视觉或交互变化必须真实浏览器检查 |
| Hermes 接口、Profile install/update、Gateway 或 Plugin context | `uv run python scripts/capability_test.py`；必要时执行真实 smoke |
| README、docs 或 AGENTS | `uv run pytest -q tests/test_documentation.py`，并检查链接与中文内容 |

真实模型 smoke 用于证明链路和协议，不是确定性单测，也不能转化为生产质量或性能指标。运行 smoke 或 Dashboard 后应停止本任务启动的进程，不要干扰用户已有服务。

## 文档要求

- `README.md` 与 `docs/**/*.md` 面向用户和开发者，说明性正文与章节标题使用中文；产品名以及必要的 API、schema、状态、命令和代码标识可以保留英文。
- 用户可见行为、启动方式、安全边界、兼容性或已知限制变化时，同步更新 README 或对应 docs。
- 真实验证记录只写可复现事实，明确区分 deterministic test、真实 smoke、历史证据、推断和未知。
- 除 `docs/VALIDATION.md` 等明确的验证记录外，不在长期设计文档或本文件写入会快速过时的测试数量、Run ID、commit hash、机器绝对路径或一次性任务状态。

## Git 与交付

- 保持改动收敛，只提交与当前需求直接相关的文件。新增依赖时同步更新 `pyproject.toml` 和 `uv.lock`。
- 不提交 `.hermes-runtime/`、`.atelier/`、`apps/.drafts/`、`dist/`、Memory、Sessions、凭据、日志或真实 Trace 导出。
- 未经用户明确要求，不执行 push、发布、公共部署、PR 创建或 Hermes 核心修改。
- 用户明确要求本地提交时，按完整能力分组；不要为每个细小编辑制造碎片提交，也不要把所有能力堆在一个提交。
- 交付前运行 `git diff --check`、检查工作树、执行密钥扫描，并说明测试结果、真实验证、剩余风险和停止的进程。

## 完成标准

只有在以下条件同时满足时才报告完成：

- 请求行为真实存在，关键成功与失败场景有测试或实际观察；
- 架构、安全、批准和路径边界未被破坏；
- 验证强度与风险相称，没有把静态检查说成真实运行；
- 文档与当前行为一致，面向人的内容保持中文；
- 未提交密钥或运行态资产，未覆盖用户无关改动；
- 已知限制、随机模型输出和未验证外部能力被如实披露。
