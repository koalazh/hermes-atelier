# Hermes Atelier V2.1

Hermes Atelier 是面向 Hermes 应用的本地开发工坊。它帮助开发者对齐业务意图、把实现交给合适的 Coding Agent、理解一组 Profiles，并交付可脱离 Atelier、通过 OpenAI-compatible HTTP 调用的 App Pack。

```text
Design through conversation
Run through Hermes
Hand off to a Coding Agent
Observe what is available
Deliver through App Packs
```

Atelier 不拥有 Agent Loop、Session、Memory、Profile 生命周期、Gateway、模型路由、通用 Chat、任务队列、Workflow 或生产部署。发布应用只依赖 Hermes、Pack 内资产，以及应用自行选择的协作原语。

## 核心路径

### Design

Builder 使用 Hermes 原生多轮 Session 对齐需求，默认产出：

- `PLAN.md`：业务目标和设计决策；
- `IMPLEMENTATION_HANDOFF.md`：给 Codex、Claude Code、Hermes、其他 Coding Agent 或人工实现者的边界、数据、权限、状态归属、交付合同、Cases、真实缺口与非目标。

默认动作是 `Export handoff`。`Generate with Hermes` 只是可选 Drafter；其 `terminal.cwd` 是工作目录提示，不是安全沙箱，生成结果仍须经过 App Pack Validator，也不会被自动采纳、安装或提交。

### Native Hermes Run

运行与对话直接使用 Hermes Chat、Session、`/v1/responses`、`/v1/chat/completions` 或 `/v1/runs`。Dashboard 只发现最近入口 Sessions 并链接/展示可见证据，不重新实现 Session 管理。

需要同步 Profile HTTP 调用时可以选择独立 `profile_call` Plugin。Trace 上报使用独立 Client 和极短 timeout；失败不会延迟 dispatch 或覆盖业务结果。Lens 区分 `complete_trace`、`partial_trace` 和 `unobserved_collaboration_possible`，没有 Trace 不表示没有 delegation、Kanban、MCP 或其他协作。

### App Pack 与 HTTP Delivery

App Pack 保持 Schema V2：逻辑 Agents、唯一 entry、Distribution、调用声明、公开 HTTP、状态声明、Cases 和 Contracts。它不包含模型、端口、Secret、部署或 Workflow。

Dashboard 以 Pack 为中心展示 Overview、Design、Sessions & Evidence、Cases、Delivery 和可选 Assurance Lab。Delivery 给出安装命令、入口 HTTP、示例调用、证据等级与限制。

### 可选 Assurance Lab

Runtime attestation、live probe、Case runner、Experiment、多 Trial、Git candidate、Reviewer、update/rollback 和供应链检查都在 Assurance Lab。普通 Demo 不必先理解或完成这些步骤。证据阶梯为：

`packed → installed → configured → runtime_attested → live_probed → cases_passed → fresh_verified`

层级可以缺失，`packed` 绝不等于“已验证发布”。

## 安装开发环境

```bash
cd /absolute/path/to/hermes-atelier
uv sync --extra dev
uv run pytest -q
uv run ruff check .
node --check plugin/atelier/dashboard/dist/index_v2.js
uv build
```

当前验证基线是 Hermes 0.19.0；版本字符串不能替代 `/health`、`/health/detailed`、`/v1/capabilities` 与 `/v1/models` 的 live probe。

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

每个物理 Profile 使用 Hermes 原生 Gateway。wrapper 提供统一默认模型的便利配置，但 Consumer 可以随后用 `hermes -p <profile> config set ...` 单独覆盖；Manifest 不承担模型管理。attestation 按 Profile 记录配置，live probe 只报告实际可确认的信息。

入口 HTTP 调用：

```bash
curl http://127.0.0.1:19300/v1/chat/completions \
  -H "Authorization: Bearer $HERMES_APP_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Session-Id: consumer-session-001' \
  -d '{"model":"support-demo--dispatcher","messages":[{"role":"user","content":"登录验证码很晚，而且订单 ORD-1001 的退款状态是什么？"}]}'
```

只应把入口端口加入 ingress。configure 为每个目标生成独立 Gateway Key，调用方只获得 self 与允许目标的映射和 Key；这减少误用，但同一 OS 用户下不是强进程隔离，`allowed_calls` 应理解为 Tool Policy 与凭据最小化。

停止：

```bash
./app stop --instance support-demo
```

`INSTALL.md` 应同时给出不使用 wrapper 的 Hermes 原生命令，避免 CLI 锁定。

## 更新语义

```bash
./app update --instance support-demo
```

update/rollback 保留为 local、best-effort、experimental。它执行 preflight、重装、映射重建和 smoke，失败时尝试恢复，但不宣称事务原子、蓝绿、远程发布、流量切换或多主机一致性。

## 四个回归 App Packs

- `apps/mini-voc`：入口自主选择不调用、调用 product、transaction 或两者；回答遵循半结构化语义约束，状态为 `session_only`。
- `apps/project-defense`：入口按需调用 source、architecture、coach；源码插件和样例源码随 source Distribution 发布，状态为 `caller_scoped`，升级需 `review_required`。
- `apps/single-profile-hello`：单 Profile、空 `allowed_calls`，不安装 `profile_call`。
- `apps/delegation-note`：使用 Hermes 原生 delegation，Pack 和 Case 不依赖固定调用树。

Atelier 核心没有任何 VOC 或答辩业务分支。

## Studio 配置

Dashboard Plugin V2 只读取下列运行态环境变量，不保存 Secret：

```bash
export ATELIER_BUILDER_URL=http://127.0.0.1:19400
export ATELIER_BUILDER_KEY_ENV=ATELIER_BUILDER_API_KEY
# 以下仅在选择可选能力时需要
export ATELIER_DRAFTER_URL=http://127.0.0.1:19401
export ATELIER_REVIEWER_URL=http://127.0.0.1:19402
```

Builder、Drafter、Reviewer 的安装和 Gateway 生命周期由 Hermes 管理。只有 Builder 是 Design 所需；Drafter 和 Reviewer 都不是 Core 启动依赖。
三个 Atelier Profile 不预设模型；安装后用 Hermes 原生 Models/config 为每个
Profile 单独配置 Provider、model 和凭据引用。Atelier 不把它们写入 App Pack。

## 状态与安全

- `.atelier/v2/designs/`：Design 对话索引、PLAN、handoff 与可选 Draft；
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
- [V2.1 核心重聚焦审计](docs/V2_1_CORE_REFOCUS.md)
- [V1 迁移](docs/MIGRATION_FROM_V1.md)
- [V2 审计计划](docs/V2_REFACTOR_PLAN.md)
- [验证记录](docs/VALIDATION.md)

## 已知边界

V2.1 是本地开发工坊，不提供多租户、企业 RBAC、生产 Trace、远程 Agent Mesh、蓝绿发布或自动优化。Atelier Lens 不是完整分布式 Trace；`terminal.cwd` 不是沙箱；相同 OS 用户下的 Key 文件不是进程隔离。真实模型 smoke 只证明链路可执行。
