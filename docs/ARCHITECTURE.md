# 总体架构

## 组件关系

```text
Hermes Dashboard
└── atelier Plugin
    ├── Dashboard Tab 与本地 FastAPI routes
    ├── atelier_call 工具
    ├── 轻量 CLI
    └── SQLite 服务

<repo>/.hermes-runtime
├── profiles/atelier-builder
├── profiles/atelier-reviewer
└── profiles/<app-id>--<role>

apps/<app-id>          版本化应用定义与 Profile Distributions
.atelier/atelier.db    Atelier 唯一状态事实源
```

每个 Profile 都运行独立的 Hermes Gateway/API Server，并绑定不同的 `127.0.0.1` 端口。Playground 请求先创建一个 Atelier Run，再使用 Session `at_<run-id>_root` 启动入口 Profile。

当入口 Agent 自主决定调用 `atelier_call` 时，Plugin 从 Hermes 调度上下文获得来源 Profile、`session_id` 和 `task_id`，校验 `allowed_calls`，创建 Span，随后使用 Session `at_<run-id>_<span-id>` 启动目标 Hermes Run。Atelier 在目标 Run 执行期间持续消费 SSE，记录真实事件，并把目标 Agent 的真实结果或错误返回给调用者。

Atelier 不代理业务推理，也不规定 Profile 拓扑。子 Agent 可以继续调用另一个被允许的 Agent，从而产生嵌套 Span。SQLite 只记录关联关系和规范化事件；每个 transcript、Memory、Skill、工具循环与 Run 仍由 Hermes 拥有。

## Build、Review 与 Proposal

Builder 只能写入 `apps/.drafts/<build-id>/`。批准操作会验证草稿中恰好存在一个应用，将其转入正式目录，使用 Hermes 原生命令安装 Distributions，写入运行态 `.env`，启动 Gateways，并注册应用。

Reviewer 只读取冻结的 Trace Bundle，不能修改应用。Proposal 应用前必须校验 Patch 中的每条路径、执行 `git apply --check` 并记录明确批准。应用成功后只更新受影响的原生 Profiles；失败时回滚源码、应用注册与已更新 Profile。用户还可以在重放比较后执行 revert。

## Dashboard 边界

Dashboard 不是常驻的 Atelier Runtime。Atelier 只添加 Build、Apps、Playground 和 Review 四个工作台视图；Profile 配置、密钥、Skills、MCP、Sessions、Chat、日志和 Gateway 管理仍由 Hermes 原生 Dashboard 负责。

停止 Dashboard 不会停止独立运行的业务 Profile Gateways，反过来停止业务 Profile 也不会删除 Dashboard 中保存的 Atelier 证据。

## 源码与运行态分离

Git 中的 Profile 目录是 Distribution 源码。运行态 Profile 位于绝对路径的项目本地 `HERMES_HOME` 下。Hermes 原生 update 负责替换 Distribution 所有的文件，并保留用户运行态的 `.env`、Memory、Sessions、凭据、日志、workspaces 和 `local/`。

Atelier 只在运行态配置中物化模型、Base URL 和绝对 `terminal.cwd`；密钥仅保留在权限为 `0600` 的 `.env` 中。应用定义、Profile 源码和运行态数据不得混在同一个目录中。

## 核心不变量

1. 所有被观测的跨 Profile 调用都经过同一个 `atelier_call`。
2. Atelier Run 只关联多个 Hermes Sessions/Runs，不替代它们。
3. `app.yaml` 只声明成员关系和调用白名单，不包含业务步骤或路由条件。
4. 正式构建和候选 Patch 都必须由后端批准状态控制。
5. `.atelier/atelier.db` 是唯一 Atelier 状态事实源；JSONL 只在主动导出时生成。
6. Trace 无法可靠落盘时必须明确标记降级，不能伪造成功。
