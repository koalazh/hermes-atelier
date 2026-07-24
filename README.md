# Hermes Atelier

Hermes Atelier 是一个**项目本地的 Hermes 多 Agent 开发工坊**：开发者用 Builder Agent 将业务描述转换为一组完整的 Hermes Profiles，在统一工作台中运行并观察真实的跨 Profile 协作，再由独立 Reviewer Agent 基于执行轨迹提出可审查的改进候选。

```text
Build → Run → Observe → Review → Propose → Approve → Replay
```

Atelier 只管理 Profile 身份、应用归属、调用白名单、运行端点、轨迹关联、文件范围和人工批准。业务理解、任务拆解、专家选择、调用顺序、工具使用和结果汇总仍由 Hermes Agent 自主完成。

它不是新的 Agent Runtime、Workflow Engine、AgentHub、生产级 Trace 平台、最终业务应用，也不替代 Hermes Dashboard。

## 适用对象

- **使用者**：希望从 Hermes Dashboard 构建、运行、观察和改进一个本地多 Agent 应用。
- **应用开发者**：希望在 `apps/<app-id>/` 中维护 Profile Distributions、SOUL、Skills、工具和验收场景。
- **Atelier 开发者**：希望修改 Plugin、状态模型、Dashboard Tab 或 Hermes 兼容层，并运行完整回归。

## 环境要求

- Hermes Agent 0.19.0 或更高版本；兼容性以能力测试结果为准，而不只看版本号。
- Python 3.11 或更高版本。
- [`uv`](https://docs.astral.sh/uv/) 和 Git。
- 一个 Hermes 可用的 OpenAI-compatible 模型端点、模型名和 API Key。

Atelier 默认只监听 `127.0.0.1`。请勿把加载了项目本地 Plugin 的 Dashboard 暴露到公网。

## 快速开始

以下命令均在仓库根目录执行：

```bash
cd /absolute/path/to/hermes-atelier
uv sync --all-extras
export HERMES_HOME="$(pwd)/.hermes-runtime"
export ATELIER_MODEL="your-model"
export ATELIER_MODEL_BASE_URL="https://your-openai-compatible-endpoint"
export OPENAI_API_KEY="your-api-key"

uv run python scripts/bootstrap.py
uv run python scripts/start.py --dashboard
```

打开 <http://127.0.0.1:9119/atelier>。

Dashboard 会在当前终端前台运行。按 `Ctrl+C` 只停止 Dashboard，不会停止已启动的 Profile Gateways；需要停止 Profiles 时再执行 `uv run python scripts/stop.py`。

`bootstrap.py` 会完成以下工作：

1. 确认运行根目录只能是当前仓库的 `.hermes-runtime`；
2. 安装 `atelier-builder`、`atelier-reviewer` 和仓库内示例应用的 Profiles；
3. 为每个 Profile 分配独立的 loopback 端口和 API Key；
4. 把模型配置和密钥写入忽略提交、权限为 `0600` 的 Profile `.env`；
5. 注册应用到 `.atelier/atelier.db`。

完成 bootstrap 后可以从当前终端移除明文环境变量：

```bash
unset OPENAI_API_KEY
```

不要把真实密钥写入 `.env.example`、`app.yaml`、Profile Distribution、Git 提交或 Issue。

## 工作台使用流程

### 1. Build

在 Build 页描述业务目标。Builder 会在 `apps/.drafts/<build-id>/` 中维护 `BUILD.md`、调查边界并生成候选应用。只有点击明确的批准按钮后，后端才会把草稿转为正式应用、安装 Profiles 并启动 Gateways。

### 2. Apps

查看应用、入口 Profile、所属 Profiles、健康状态、端点、缺失环境变量和定义版本。SOUL、Skill、密钥、MCP 和 Hermes 配置继续通过本地编辑器或 Hermes 原生 Dashboard 管理。

### 3. Playground

选择应用和保存场景，或输入临时请求。Playground 会创建一个 Atelier Run，并实时显示入口输出、真实跨 Profile 调用树、Span、Hermes Run ID、必要事件和失败状态。所有被观测的跨 Profile 调用都必须经过 `atelier_call`。

### 4. Review

为一个或多个 Run 添加人工反馈，冻结 Trace Bundle，再调用只读 Reviewer。Reviewer 只能输出证据、推断、不确定性和建议；Builder 只能生成候选 Patch。完整 Diff 必须经过人工批准才能应用，随后可重放原场景并比较前后结果。

## 示例应用

仓库包含两个使用同一套 Atelier 核心的示例：

- `mini-voc`：Dispatcher 按需调用 Product 或 Transaction 专家，也可以直接回答或追问。
- `project-defense`：Host 按需调用 Source、Architecture 和 Coach；Source 只读指定源码工作区。

运行真实 smoke scenario：

```bash
uv run python scripts/smoke_test.py mini-voc --scenario clarify.yaml
uv run python scripts/smoke_test.py project-defense --scenario evidence-gap.yaml
```

真实模型输出具有随机性。Smoke 通过只能证明链路可执行，不能证明业务答案始终正确。

## 常用运维命令

```bash
# 查看所有 Profile 端点和状态
uv run python scripts/status.py

# 只启动指定应用；Builder 和 Reviewer 仍会启动
uv run python scripts/start.py --app mini-voc

# 启动全部 Profile 和前台 Dashboard，并指定本地端口
uv run python scripts/start.py --dashboard --dashboard-port 9119

# 停止 Atelier 管理的所有 Profile Gateways
uv run python scripts/stop.py
```

Dashboard 与业务 Profile Gateways 相互独立：Dashboard 停止后，已经启动的业务 HTTP Agents 仍能继续运行。

## 本地数据与清理

以下目录均被 Git 忽略：

- `.hermes-runtime/`：项目本地 Hermes Profiles、Memory、Sessions、密钥、日志和运行状态；
- `.atelier/`：唯一 Atelier SQLite 数据库、Trace Bundles、Reviews、Proposals 和诊断日志；
- `apps/.drafts/`：Builder 与 Proposal 的隔离草稿。

删除这些目录会删除本地运行状态。执行前应先停止 Gateways；删除操作不可恢复：

```bash
uv run python scripts/stop.py
```

Atelier 的 `HERMES_HOME` 只是 Hermes 状态隔离边界，不是操作系统安全沙箱。需要更强文件、进程或网络隔离的 Profile，应使用 Hermes 支持的 Docker 等执行后端。

## 开发与验证

Coding Agent 在修改仓库前应先阅读根目录的 [`AGENTS.md`](AGENTS.md)。其中记录了不可破坏的架构不变量、目录职责、安全边界、Bugfix 流程与分层验证要求。

```bash
uv sync --extra dev

# 完整回归
uv run pytest -q

# 七阶段确定性闭环测试
uv run pytest -q tests/test_full_workflow.py

# 静态检查、Dashboard bundle 语法和构建
uv run ruff check .
node --check plugin/atelier/dashboard/dist/index.js
uv build

# 当前 Hermes 安装与项目本地运行态能力探针
uv run python scripts/capability_test.py
```

新增应用时，只修改 `apps/<app-id>/`：提供极简 `app.yaml`、完整 Profile Distributions 和场景。不要在 Atelier Plugin、数据库或 Dashboard 中加入业务路由特判。详见[架构说明](docs/ARCHITECTURE.md)和[Builder 设计](docs/BUILDER.md)。

## 故障排查

- **`profile_unhealthy`**：先运行 `scripts/status.py`，再查看 `.atelier/logs/<profile>.log`；确认端口未占用、模型端点可达、环境变量完整。
- **`incompatible_hermes`**：运行 `scripts/capability_test.py`，确认 Hermes 能向 Plugin handler 传递匹配的 `task_id`、`session_id` 和来源 Profile。
- **HTTP 401/403**：重新执行 bootstrap 写入运行态凭据；浏览器不会也不应直接获得 Profile API Key。
- **HTTP 429**：这是模型供应商拒绝或限流，不应通过 Atelier 伪造成功结果；检查供应商账号、模型名、配额和官方 API Base URL。
- **`call_not_allowed`**：检查当前应用 `app.yaml` 的 `allowed_calls`。它是安全白名单，不是业务路由规则。
- **`trace_degraded`**：真实 Agent 调用可能已完成，但部分事件未能可靠写入；不要把它当作完整 Trace。
- **Proposal 无法应用**：确认 Patch 只修改当前 `apps/<app-id>/`，且工作树没有与 Patch 冲突的本地修改。

## 文档导航

- [项目立意与非目标](docs/PROJECT.md)
- [总体架构](docs/ARCHITECTURE.md)
- [Builder、Reviewer 与批准边界](docs/BUILDER.md)
- [Trace 数据模型](docs/TRACE_MODEL.md)
- [安全边界](docs/SECURITY.md)
- [真实验证证据与已知限制](docs/VALIDATION.md)
- [初始审计与重构计划](docs/REFACTOR_PLAN.md)
- [架构决策记录](docs/adr/)

## 当前交付边界

Hermes Atelier V1 面向可信仓库中的本地开发，不提供公网部署、多租户、企业 RBAC、生产级 Trace、自研 Runtime、自动自进化或自动发布。若 Hermes 原生补齐对应能力，应优先删除 Atelier 的重复模块。
