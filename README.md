# Hermes Atelier V2

Hermes Atelier 是一个面向多 Profile Hermes 应用的开发工坊：通过多轮 Builder 会话形成设计，直接使用 Hermes Session 运行应用，以真实 `profile_call` 元数据观察协作，用 Case/Experiment 评测行为，并发布为不依赖 Atelier 的 Hermes App Pack。

```text
Design through conversation
Run through Hermes
Observe through Atelier
Evaluate through cases
Change through Git
Deliver through App Packs
```

Atelier 不是 Agent Runtime、Workflow Engine、AgentHub、Profile Manager、Gateway Supervisor、包管理平台或生产控制面。发布应用只依赖 Hermes、App Pack 内的 Profile Distributions、业务 Plugins，以及应用自己选择的协作原语。

## 核心路径

### Design

Builder 是完整 Hermes Profile。Studio 使用 Hermes 原生 `/api/sessions/{id}/chat` 进行多轮对齐：Builder 可以提问，开发者可以回答、纠正目标或要求简化。只有 `DESIGN_STATUS: PLAN_READY` 后，显式 `Generate Draft` 才会调用拥有写权限的 Draft Profile。规划 Profile 默认禁用文件、终端、代码执行、历史 Session 搜索和跨 Agent 委派。

Draft 生成不是 adopt、install、commit 或 approve。候选修改通过 Git branch/worktree、明确 Diff 和 Experiment 管理，Atelier 不再对当前工作树执行 `git apply`。

### Run & Observe

开发者直接使用 Hermes Chat、`/api/sessions/{id}/chat`、`/v1/chat/completions`、`/v1/responses` 或 `/v1/runs`。Atelier 不包装通用 Chat/Session/Run 生命周期。

需要跨 Profile HTTP 协作的应用可选择独立 `profile_call` Plugin。它从 Profile 本地 `local/app-runtime.json` 解析逻辑 Agent，校验 `allowed_calls`，调用目标 Hermes Run，并返回真实目标 Profile、Session 和 Run 元数据。Trace Sink 是可选的；Trace 故障不会阻断业务调用。

### Evaluate

Case 只描述输入、初始状态、`clean | session_only | retained` Memory Policy、少量通用结果断言和人工评价提示，不描述 Workflow。Experiment 冻结：

- App Pack revision；
- Profile Definition Snapshot；
- 模型与 Provider 指纹；
- 不可变 Case 与 Memory Policy；
- 一个或多个 Trial；
- Hermes Session/Run 与真实 Trace；
- 自动断言和人工反馈。

Reviewer 分析整个 Experiment，只输出诊断、假设、不确定性、风险和验证建议，不能根据一次结果宣称优化完成。

### Release

App Pack 是普通目录或 Git 仓库。发布物包含 `app.yaml`、Hermes Profile Distributions、业务 Plugins、Cases、Contracts、文档、薄 `./app` 和 `app.lock`；不包含 `.env`、密钥、Memory、Sessions、Trace、PID、`local/` 或 Atelier DB。

## 安装开发环境

```bash
cd /absolute/path/to/hermes-atelier
uv sync --all-extras
uv run pytest -q
uv run ruff check .
node --check plugin/atelier/dashboard/dist/index_v2.js
uv build
```

Hermes 最低兼容版本为 0.19.0。版本字符串不能替代真实能力探针。

## 验证与发布一个 Pack

示例不会默认安装或启动：

```bash
uv run atelier validate apps/mini-voc
uv run atelier cases apps/mini-voc
uv run atelier release apps/mini-voc /tmp/mini-voc-release --git-revision HEAD
```

接收方不需要 Atelier。以 Mini VOC 为例：

```bash
cd /tmp/mini-voc-release
export HERMES_HOME=/absolute/fresh/hermes-home
export DEEPSEEK_API_KEY='set-in-your-shell'
export HERMES_APP_API_KEY='use-a-long-random-secret'

./app install --instance support-demo
./app configure \
  --instance support-demo \
  --model deepseek-v4-flash \
  --model-base-url https://api.deepseek.com \
  --model-key-env DEEPSEEK_API_KEY \
  --gateway-key-env HERMES_APP_API_KEY \
  --gateway-port 19300
./app start --instance support-demo
./app status --instance support-demo
```

每个物理 Profile 使用一个 Hermes 原生 Gateway 和显式本地端口。薄 wrapper 只代理 Hermes install/config/gateway/update 命令并生成逻辑映射；Hermes 仍拥有 PID、launchd、健康、Session、Memory 和 Run。当前 Hermes multiplex 的 Plugin Manager 是进程级单例，不能隔离示例所需的 Profile 私有 Plugins，因此 V2 不使用 multiplex。

入口 HTTP 调用：

```bash
curl http://127.0.0.1:19300/v1/chat/completions \
  -H "Authorization: Bearer $HERMES_APP_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Session-Id: consumer-session-001' \
  -d '{"model":"support-demo--dispatcher","messages":[{"role":"user","content":"登录验证码很晚，而且订单 ORD-1001 的退款状态是什么？"}]}'
```

只应把入口 Agent 的端口加入对外 ingress。内部 Agent 端口、认证和网络策略由 Consumer 部署负责。

停止：

```bash
./app stop --instance support-demo
```

`INSTALL.md` 应同时给出不使用 wrapper 的 Hermes 原生命令，避免 CLI 锁定。

## 更新语义

```bash
./app update --instance support-demo
```

更新执行 preflight、停止受影响 Profile、安装新 Distributions、清理被删除 Profile、重建映射、启动、运行 Pack 的首个 smoke Case；失败会报告失败并 best-effort 恢复旧 Distribution、映射与服务。更新保留 Consumer 的 `.env`、Memory、Sessions 和 `local/`。`state_compatibility` 会标记 `preserve`、`review_required` 或 `reset_recommended`，但不会偷偷重置状态。

## 两个回归应用

- `apps/mini-voc`：入口自主选择不调用、调用 product、transaction 或两者；有结构化输出 Contract，状态为 `session_only`。
- `apps/project-defense`：入口按需调用 source、architecture、coach；源码插件和样例源码随 source Distribution 发布，状态为 `caller_scoped`，升级需 `review_required`。

Atelier 核心没有任何 VOC 或答辩业务分支。

## Studio 配置

Dashboard Plugin V2 只读取下列运行态环境变量，不保存 Secret：

```bash
export ATELIER_BUILDER_URL=http://127.0.0.1:19400
export ATELIER_BUILDER_KEY_ENV=ATELIER_BUILDER_API_KEY
export ATELIER_DRAFTER_URL=http://127.0.0.1:19401
export ATELIER_DRAFTER_KEY_ENV=ATELIER_DRAFTER_API_KEY
export ATELIER_REVIEWER_URL=http://127.0.0.1:19402
export ATELIER_REVIEWER_KEY_ENV=ATELIER_REVIEWER_API_KEY
```

Builder、Drafter、Reviewer 的安装和 Gateway 生命周期仍用 Hermes 原生命令管理。Studio 不在 Dashboard 进程创建后台 Agent Runtime。

## 状态与安全

- `.atelier/v2/designs/`：Design 对话索引、PLAN 与 Draft；
- `.atelier/v2/traces/`：best-effort 真实 `profile_call` 事件索引；
- `.atelier/v2/experiments/`：冻结的 Experiment 开发证据；
- Consumer Profile `.env`：Secret；
- Consumer Profile `local/app-runtime.json`：无 Secret 的逻辑映射；
- Hermes Profile 目录：Memory、Sessions、Run、PID 与日志。

删除 Atelier Dashboard 或 `.atelier` 不影响已经发布和安装的应用。真实密钥不得进入源码、测试 fixture、日志、Trace、`app.lock`、文档或 Git。

## 文档

- [项目定位](docs/PROJECT.md)
- [V2 架构](docs/ARCHITECTURE.md)
- [App Pack 合同](docs/APP_PACK.md)
- [profile_call](docs/PROFILE_CALL.md)
- [Case 与 Experiment](docs/CASES_AND_EXPERIMENTS.md)
- [发布和更新](docs/RELEASE.md)
- [V1 迁移](docs/MIGRATION_FROM_V1.md)
- [V2 审计计划](docs/V2_REFACTOR_PLAN.md)
- [验证记录](docs/VALIDATION.md)

## 已知边界

V2 是本地开发工坊，不提供多租户、企业 RBAC、生产 Trace、远程 Agent Mesh、蓝绿发布或自动优化。真实模型输出具有随机性；smoke 只证明链路可执行，不能证明生产质量、性能或业务正确率。
