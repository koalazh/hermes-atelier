# Hermes Atelier V1 审计与重构计划

## 1. 审计基线

审计日期：2026-07-24

仓库：`/Users/koala/work/product/hermes-atelier`

被检查的 Hermes 运行环境：

- 版本：Hermes Agent `0.19.0`（`2026.7.20`）；
- 上游 commit：`9eb7b1a6b1ffdd4ad1a85aee3f38edceee2b927f`；
- 安装目录：`/Users/koala/.hermes/hermes-agent`；
- 安装方式：Git checkout；
- 本地状态：比上游落后一个 commit；
- Hermes checkout 原有改动：`package-lock.json` 已修改，`.install_method` 未跟踪。

Hermes checkout 只作为本项目的只读证据。Atelier 不更新、修改或吸收其中已有的未提交文件。

审计开始时，Atelier 仓库是一个已初始化、工作树干净、没有 commit、没有任何项目文件的空 Git 仓库。因此不存在需要保留、迁移或删除的旧 Atelier 实现。正确做法是针对当前 Hermes 公共接口从零实现克制的 V1，而不是为不存在的旧代码建立兼容层。

## 2. 现有资产分类

| 分类 | 当时资产 | 决策 |
| --- | --- | --- |
| `KEEP` | 无 | 仓库为空。 |
| `CONVERT_TO_ATELIER_PLUGIN` | 无 | 按 V1 合同创建一个 `atelier` Plugin，不增加并行常驻服务。 |
| `CONVERT_TO_BUILDER_ASSET` | 无 | 创建完整 `atelier-builder` Profile Distribution 与薄 Builder Skill。 |
| `CONVERT_TO_REVIEWER_ASSET` | 无 | 创建完整、独立的 `atelier-reviewer` Profile Distribution 与只读 Reviewer Skill。 |
| `KEEP_AS_EXAMPLE` | 无 | 新建 Mini VOC 与 Project Defense；所有业务行为留在各自 Profiles、SOULs、Skills 与工具中。 |
| `DELETE` | 无 | 没有仓库内容需要删除；运行态目录只加入忽略规则。 |
| `VERIFY_AGAINST_CURRENT_HERMES` | 以下所有集成面 | 以已安装 Hermes 0.19.0 源码和真实 smoke 为兼容性判据。 |

## 3. 当前 Hermes 能力审计

### 3.1 从已安装 0.19.0 源码确认的能力

| 能力 | Hermes 中的证据 | Atelier 决策 |
| --- | --- | --- |
| 自定义根目录与命名 Profile 隔离 | `hermes_constants.get_default_hermes_root()` 把自定义 `HERMES_HOME` 作为根目录，命名 Profiles 位于 `<root>/profiles/<name>`；`-p` 在运行时 import 前解析。 | 每个 Atelier 子进程显式获得仓库绝对 `.hermes-runtime` 和 `-p <profile>`，不使用 sticky active Profile。 |
| Profile Distribution install/update | `hermes_cli/profile_distribution.py` 支持带 `distribution.yaml` 的本地目录。Distribution 文件会更新，而 `.env`、Memory、Session DB、凭据、日志、workspaces 与 `local/` 受保护；除非显式 `--force-config`，否则保留 `config.yaml`。 | 版本化 Distribution 源码留在仓库，使用 Hermes 原生 install/update，不自行复制 Hermes 用户状态。 |
| Plugin 工具注册 | `PluginContext.register_tool()` 向原生 registry 注册 schema/handler，registry dispatch 会把运行时 kwargs 传给 handler。 | 只注册 `atelier_call`，不建立远程 Agent Registry 或 Workflow 工具族。 |
| 工具执行上下文 | `model_tools.py` 调用 Plugin tool 时传入 `task_id` 和 `session_id`；`PluginContext.profile_name` 解析当前来源 Profile。 | 注册时捕获来源 Profile，并要求非空且匹配的 `task_id`/`session_id`；不兼容时失败关闭。 |
| 项目/用户 Plugin 发现 | Hermes 扫描 root/profile `plugins/` 和项目 `./.hermes/plugins/`，并通过 `plugins.enabled` 显式启用。 | `bootstrap.py` 把可信仓库 Plugin 链接到 root 和各运行 Profile；源码仍以 `plugin/atelier` 为准。 |
| Dashboard Plugin 后端 | Dashboard manifest 可声明 `plugin_api.py`，Hermes 将 `APIRouter` 挂载到 `/api/plugins/<manifest-name>/`。 | 所有 Atelier 本地 routes 都由同一个 Plugin API 模块提供。 |
| Dashboard Plugin 前端 | bundle 通过 `window.__HERMES_PLUGINS__` 注册；`window.__HERMES_PLUGIN_SDK__` 提供 React、hooks、基础组件和认证 API client。 | 发布不自带 React 的 IIFE bundle，只调用 SDK。 |
| API Server Sessions | `/api/sessions` 提供 create/get/messages/fork/chat。 | Hermes 继续拥有 transcript；Trace export 只读取被引用 Session。 |
| API Server Runs | `POST /v1/runs` 接受 `input`、可选 `instructions`、`session_id`、conversation history 和 `X-Hermes-Session-Key`，返回 `202` 与 `run_id`。 | Root/child 显式使用 Atelier transcript Session ID；长期 Memory scope 单独传递。 |
| Run 观察与控制 | `GET /v1/runs/{id}/events` 以 SSE 输出到终态；GET 查询状态，POST stop 返回 `stopping`，approval route 处理工具批准。终态记录有有限 TTL。 | 执行期间消费并立即保存规范化事件；stop 请求不等于已停止。 |
| 独立 API Servers | Hermes Gateway 支持每 Profile API Server、必需 Key 和 loopback bind guard。 | V1 为每个 Profile 分配独立本地端口和密钥，写入忽略的 `.env` 并独立启停。 |
| Dashboard/Profile 管理 | Hermes Dashboard 已提供 Profile switcher、Config、凭据、Skills、MCP、Sessions、Chat、日志与 Gateway 管理。 | Atelier 只链接原生管理页，不重做这些编辑器。 |

### 3.2 宣称兼容前必须完成的能力测试

源码检查只能证明预期接口，不能证明当前安装的运行接线。实现必须直接验证：

1. 注册的 `atelier_call` handler 收到 Hermes 0.19.0 dispatch 的精确 `task_id` 与 `session_id`，并解析当前 Profile；
2. 绝对自定义 `HERMES_HOME` 把本地 Distribution 安装到 `.hermes-runtime/profiles/<name>`，不触碰 `~/.hermes`；
3. Distribution update 保留 `.env` marker 与 Hermes 自有 Session 状态；
4. 每个 Profile 的独立 Gateway 只绑定分配的 `127.0.0.1` 端口，并通过 health/capability 检查；
5. Sessions、Runs、SSE terminal events、stop 与 API auth 符合源码接口；
6. Dashboard 能发现 root `atelier` manifest、挂载 `plugin_api.py` 并加载 SDK-only bundle；
7. Root Agent 与 child `atelier_call` 在 SQLite 中产生真实且关联的 Hermes Run IDs 与 Session IDs。

若第 1 项失败，`atelier_call` 必须返回结构化 `incompatible_hermes`，并在文档提高最低版本；不得新增旁路 Runtime，也不得信任自然语言 Run ID。

以上七组能力均于 2026-07-24 实测。Run、Review、Proposal、浏览器与限制证据见 `docs/VALIDATION.md`。

## 4. 重复实现分析

以下内容会重复 Hermes，因此不实现：

- Profile Registry 或自定义 Profile 目录格式；
- Session/transcript Store；
- Agent 执行循环或模型路由；
- Memory、Skill、MCP、Plugin、凭据或 Gateway 管理页面；
- 通用远程 Agent Mesh；
- Workflow 图、步骤执行器、业务重试、Router、fan-out、aggregate 或 judge 原语；
- 第二个 Dashboard Server 或常驻 Atelier daemon；
- 对全部数据库事件再做一份 JSONL 镜像。

Atelier 只补充缺失的开发工坊边界：

- 版本化应用成员与调用白名单；
- 不向浏览器暴露密钥的运行 Endpoint 引用；
- 可信、可观测的跨 Profile 调用接缝；
- 关联多个 Profile-local Hermes Sessions/Runs 的 Atelier Run；
- Build/Review/Proposal 批准状态与路径受限 Patch；
- 覆盖以上本地操作的薄 Dashboard Tab。

## 5. 目标实现映射

仓库最终收敛为四组核心资产：

1. `plugin/atelier/`：可信 Hermes Plugin，包含 `atelier_call`、CLI、SQLite Services、Dashboard routes 与 SDK-only bundle；
2. `profiles/atelier-builder/` 和 `profiles/atelier-reviewer/`：完整 Profile Distribution 源码；
3. `apps/<app-id>/`：默认不可变的应用定义、Profile Distributions、Skills 与场景；
4. 被忽略的 `.hermes-runtime/` 和 `.atelier/`：Hermes 运行态、Atelier SQLite、Proposal 与 export 状态。

Python 模块可以按经过测试的边界继续拆分，但不能引入第二个常驻进程或第二个权威状态源。

## 6. 兼容性决策

- 最低 Hermes 版本从 `>=0.19.0` 开始；最终由能力检查而非版本字符串判断兼容。
- 保持 Hermes 原生 manifest 名称 `distribution.yaml`，不增加 Atelier Distribution wrapper。
- Git 中的 `plugin/atelier` 是源码；运行安装优先使用本地 symlink，失败时安全复制，运行副本不提交。
- Root/child transcript ID 使用 `at_<run-id>_root` 与 `at_<run-id>_<span-id>`；解析器只接受 SQLite 中存在的 Atelier 标识。
- 调用者 Profile 来自 Hermes Plugin context，不来自工具参数；`target` 必须通过当前应用 revision 的白名单。
- API Key 只留在忽略的 Profile `.env`；Endpoint Registry 只保存 host、port、status 与 PID，API 不返回密钥或 `.env` 内容。
- SQLite 写失败标记 `trace_degraded`。授权或父子关联不能在 dispatch 前持久化时直接拒绝；dispatch 后事件降级时返回真实下游结果和明确降级元数据。
- HTTP 重试只限幂等连接或读取；Atelier 不选择备用专家，也不实现业务重试。

## 7. 构建顺序与验证门槛

构建按完整能力而非文件数量推进：

1. Plugin 骨架、schema 校验、SQLite、App Registry；
2. 项目本地 Hermes root bootstrap 与 Profile 生命周期；
3. `atelier_call`、Hermes HTTP Client、Run/Span/Event、脱敏与错误；
4. Dashboard Build/Apps routes 与 UI；
5. Playground、SSE 与 Trace tree；
6. Builder draft contract 与明确批准安装；
7. Reviewer、冻结 Trace Bundle、Proposal validate/apply/reject 与 Replay；
8. 使用同一核心完成 Mini VOC 和 Project Defense；
9. 安全、降级、文档、完整回归、真实 Hermes smoke、浏览器检查与对抗式完成审查。

每项能力只在对应测试通过后提交。Push、发布、公网监听与 Hermes 核心修改不在仓库授权范围内。

## 8. 审计结论

仓库中没有旧 Atelier 代码需要重构。Hermes 0.19.0 已提供该设计所需的 Runtime、Profile 隔离与 Distribution、Sessions、Memory、Skills、Plugins、独立 Gateways/API Servers、Runs/SSE 与 Dashboard 扩展宿主。

因此 Hermes Atelier V1 应保持为一个刻意精简的本地 Plugin、版本化 Profile 资产与一个关联数据库。任何新增 Workflow Engine 或重复 Hermes 管理页面的实现都会同时违背产品合同和当前运行证据。
