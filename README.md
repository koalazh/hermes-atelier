# Hermes Atelier

**把一句业务需求，交接给 Coding Agent 实现成一组 Hermes Profiles，并最终交付为其他系统可通过 HTTP 调用的应用。**

例如，你想做一个“能判断客户反馈属于产品问题还是退款问题，并在需要时查询对应专家”的助手。Hermes Atelier 帮你完成的不是一次聊天，而是下面这套可交付结果：

- 与 Builder 多轮讲清目标、边界和验收条件；
- 导出 `PLAN.md` 和 `IMPLEMENTATION_HANDOFF.md`，交给 Codex、Claude Code、Hermes 或人工实现；
- 把实现组织成可验证的 App Pack；
- 用 Hermes 原生 Profile、Session、Gateway 运行；
- 交付一个不依赖 Atelier 的 OpenAI-compatible HTTP 服务。

Atelier 是开发工坊，不是应用 Runtime。Dashboard 关闭、`.atelier` 删除、Builder 未安装时，已经交付的应用仍由 Hermes 独立运行。

## 先理解完整链路

```text
业务需求
   │
   ▼
Atelier Builder 多轮对齐
   │  产出 PLAN.md + IMPLEMENTATION_HANDOFF.md
   ▼
你选择的 Coding Agent 实现
   │  产出 apps/<pack-id>/
   ▼
Atelier 验证并打包 App Pack
   │  产出可搬走的 release 目录
   ▼
Consumer 用 Hermes 安装并启动 Profiles
   │
   ▼
其他系统通过 /v1/chat/completions 或 /v1/responses 调用
```

这里有三个不同角色：

| 角色 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| Hermes Atelier | 需求对齐、Coding Agent handoff、App Pack 验证、交付说明和可选证据 | 不运行 Agent Loop，不管理生产部署 |
| Coding Agent | 根据 handoff 编写 Profile、Skill、Plugin、Case 和 App Pack 文件 | 不替用户决定未对齐的业务目标 |
| Hermes | Profile、模型、工具、Session、Memory、Gateway 和真实请求运行 | 不替 Atelier 定义应用交付边界 |

## 我应该从哪里开始

### 我只想先看看它能不能跑

从最小单 Profile 示例开始。它不需要 Builder、Dashboard 或 `profile_call`：

```bash
uv sync --extra dev
uv run atelier validate apps/single-profile-hello
uv run atelier release \
  apps/single-profile-hello \
  /tmp/single-profile-hello-release \
  --git-revision HEAD
```

然后进入 release 目录，使用 `./app install/configure/start` 启动 Hermes Gateway，并用 curl 调用。完整、可复制的命令见[首次上手：路径 A](docs/GETTING_STARTED.md#路径-a先跑通一个已存在的-app-pack)。

### 我想从自己的需求创建应用

按下面的主路径走：

1. 安装 Atelier Dashboard Plugin 和只读 Builder Profile；
2. 在 Dashboard 的 **Atelier → Design** 输入原始需求；
3. 与 Builder 多轮确认目标，直到得到 PLAN 和 handoff；
4. 默认选择 **Export handoff**，交给你信任的 Coding Agent；
5. Coding Agent 在 `apps/<pack-id>/` 实现 App Pack；
6. 执行 validate、release、install、start；
7. 用普通 OpenAI-compatible HTTP 调用入口 Profile。

从安装 Builder 到首个 HTTP 请求的完整说明见[首次上手：路径 B](docs/GETTING_STARTED.md#路径-b从自己的业务需求创建应用)。

## 你最终会得到什么

一个 App Pack 是一个普通目录，而不是运行中的平台对象：

```text
apps/<pack-id>/
├── app.yaml                 # 应用入口、Profiles、调用与状态声明
├── README.md                # 业务说明
├── INSTALL.md               # Consumer 安装和 HTTP 使用方式
├── profiles/                # Hermes Profile Distributions
├── cases/                   # 可选验收 Cases
└── contracts/               # 可选公共输出合同
```

`atelier release` 会生成可独立搬运的 release。接收方只需要 Hermes、模型凭据和 release 内资产，不需要仓库、Dashboard、`.atelier`、Builder、Drafter 或 Reviewer。

## 最短日常工作流

```bash
# 1. Coding Agent 完成实现后，检查 Pack 结构
uv run atelier validate apps/<pack-id>

# 2. 查看已声明的 Cases；需要时再真实运行
uv run atelier cases apps/<pack-id>

# 3. 生成不可变交付目录，目标目录必须尚不存在
uv run atelier release \
  apps/<pack-id> \
  /absolute/path/to/<pack-id>-release \
  --git-revision HEAD

# 4. Consumer 在 release 目录安装并启动
cd /absolute/path/to/<pack-id>-release
./app install --instance <instance-name>
./app configure --instance <instance-name> [模型和 Gateway 参数]
./app start --instance <instance-name>
```

每个 Pack 生成的 `INSTALL.md` 会给出它自己的 Profile 名、端口和完整 HTTP 示例。不要从其他 Pack 猜这些值。

## Core 与 Assurance Lab

第一次做 Demo 只需要 Core：

`Design → Coding Agent handoff → App Pack → Hermes Run → HTTP Delivery`

以下能力都不是启动应用的前置条件，它们只在需要更高可信度时使用：

- configured runtime attestation 与 live probe；
- Case、Experiment、多 Trial 和 Reviewer；
- Candidate Git binding 与 release provenance；
- update/rollback、Secret 和供应链检查。

Dashboard 中这些能力统一放在 **Assurance Lab**。证据等级只说明已经获得哪些证据，`packed` 不等于“生产可用”，没有 Trace 也不等于 Agent 没有协作。

## 四个可以参考的 App Packs

| Pack | 适合学习什么 |
| --- | --- |
| `apps/single-profile-hello` | 最小单 Profile HTTP 应用，不安装 `profile_call` |
| `apps/mini-voc` | 一个入口按业务需要调用两个专家 |
| `apps/project-defense` | 带源码证据、工具和 caller scope 的多 Profile 应用 |
| `apps/delegation-note` | 使用 Hermes 原生 delegation，不依赖固定 Trace 调用树 |

如果你第一次实现新 Pack，先复制 `single-profile-hello` 的目录心智模型，而不是从最复杂的 Assurance 能力开始。

## 开发仓库

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
node --check plugin/atelier/dashboard/dist/index_v2.js
uv build
```

当前验证基线为 Hermes 0.19.0。Atelier 不修改 Hermes 核心。

## 按任务查文档

- **第一次跑通或创建应用**：[GETTING_STARTED.md](docs/GETTING_STARTED.md)
- **理解产品边界和职责**：[PROJECT.md](docs/PROJECT.md)
- **理解 Builder、handoff、Drafter 和 Reviewer**：[BUILDER.md](docs/BUILDER.md)
- **编写 `app.yaml` 和 App Pack**：[APP_PACK.md](docs/APP_PACK.md)
- **发布、安装、HTTP 调用和停止**：[RELEASE.md](docs/RELEASE.md)
- **选择跨 Profile 协作方式**：[PROFILE_CALL.md](docs/PROFILE_CALL.md)
- **需要 Case 或 Experiment 时**：[CASES_AND_EXPERIMENTS.md](docs/CASES_AND_EXPERIMENTS.md)
- **理解安全边界**：[SECURITY.md](docs/SECURITY.md)
- **查看真实验证记录**：[VALIDATION.md](docs/VALIDATION.md)
- **从 V1 迁移**：[MIGRATION_FROM_V1.md](docs/MIGRATION_FROM_V1.md)

## 当前不提供什么

Hermes Atelier V2.1 不提供生产部署、多租户、企业 RBAC、远程 Registry、流量切换或完整分布式 Trace。`allowed_calls` 是正常工具路径上的策略与凭据最小化，不是 OS/网络隔离；update/rollback 是 local、best-effort、experimental。
