# 首次上手：从需求到 HTTP App Pack

这份指南只解决一个问题：**怎样真正完成一次 Hermes Atelier 开发闭环。**

你可以选择两条路径：

- 路径 A：先运行仓库中已有的最小 App Pack，理解最终交付物；
- 路径 B：从自己的业务需求开始，经 Builder、Coding Agent、App Pack 到 HTTP。

如果还没有使用过 Hermes，建议先走路径 A。它不依赖 Atelier Dashboard，也不会让 Assurance Lab 概念干扰第一次体验。

## 完成后的样子

无论选择哪条路径，最终成功标准都相同：

1. 有一个通过 `atelier validate` 的 `apps/<pack-id>/`；
2. 有一个由 `atelier release` 生成、可搬离源码仓库的 release 目录；
3. Consumer 能在自己选择的 `HERMES_HOME` 中安装和启动 Profiles；
4. curl 或其他 OpenAI-compatible Client 能调用唯一入口；
5. 停止 Atelier Dashboard 或删除 `.atelier` 后，应用请求仍然成功。

## 前置条件

- Hermes Agent 0.19.0 或与 Pack 声明兼容的版本；
- Python 3.11+ 和 `uv`；
- 一个已经在 Hermes 中可用的模型 Provider，或它的 Base URL、模型名和 API Key；
- 当前仓库 checkout。

先安装项目开发依赖：

```bash
cd /absolute/path/to/hermes-atelier
uv sync --extra dev
```

真实 Secret 只放在 shell 或 Hermes Profile `.env`，不要写入 `app.yaml`、Case、Trace、文档或 Git。

## 路径 A：先跑通一个已存在的 App Pack

这里使用 `single-profile-hello`。它只有一个公开 Profile，没有内部专家，也不安装 `profile_call`，最适合看清基本链路。

### 1. 验证和生成 release

```bash
uv run atelier validate apps/single-profile-hello
uv run atelier cases apps/single-profile-hello
uv run atelier release \
  apps/single-profile-hello \
  /tmp/single-profile-hello-release \
  --git-revision HEAD
```

release 目标目录必须尚不存在。成功后，`/tmp/single-profile-hello-release` 可以单独复制到另一台安装了 Hermes 的机器；它不需要 Atelier Dashboard。

### 2. 安装并配置 Hermes Profile

下面用 DeepSeek-compatible 配置演示；只需填入自己的 Key。若使用其他 Provider，替换模型名和 Base URL：

```bash
cd /tmp/single-profile-hello-release

export HERMES_HOME=/absolute/path/to/consumer-hermes-home
export MODEL_API_KEY='<your-deepseek-api-key>'
export HERMES_APP_API_KEY='<a-long-random-gateway-key>'

./app install --instance hello-demo
./app configure \
  --instance hello-demo \
  --model 'deepseek-v4-flash' \
  --model-base-url 'https://api.deepseek.com' \
  --model-key-env MODEL_API_KEY \
  --gateway-key-env HERMES_APP_API_KEY \
  --gateway-port 19300
./app start --instance hello-demo
./app status --instance hello-demo
```

`./app` 是安装便利 wrapper，不是 Atelier Runtime。它最终调用的是 Hermes 原生 Profile 和 Gateway 生命周期能力。

### 3. 从普通 HTTP Client 调用

```bash
curl http://127.0.0.1:19300/v1/chat/completions \
  -H "Authorization: Bearer $HERMES_APP_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Session-Id: hello-session-001' \
  -d '{"model":"hello-demo--hello","messages":[{"role":"user","content":"你好，我是第一次调用这个应用"}]}'
```

看到 Hermes 返回的 Chat Completions JSON，就已经完成最小闭环。此时 Atelier Dashboard 没有参与请求链。

停止应用：

```bash
./app stop --instance hello-demo
```

停止不会删除 Profile、Session 或 Memory。若要删除，必须由 Consumer 使用 Hermes 原生命令明确删除物理 Profile。

## 路径 B：从自己的业务需求创建应用

这条路径分成六个阶段。每个阶段都有明确输入、产物和责任人。

| 阶段 | 你的输入 | 产物 | 主要责任人 |
| --- | --- | --- | --- |
| 1. Design | 原始业务需求 | 对齐后的目标 | 你 + Builder |
| 2. Handoff | 多轮确认结果 | PLAN + IMPLEMENTATION_HANDOFF | Builder |
| 3. Implementation | handoff | `apps/<pack-id>/` | 你选择的 Coding Agent |
| 4. Pack | App Pack 源码 | validate 通过 | Atelier CLI |
| 5. Native Run | release + 模型/端口/Secret | Hermes Profiles/Gateways | Hermes + Consumer |
| 6. Delivery | 入口 URL 和 Key | 下游 HTTP 调用 | Consumer |

### 阶段 1：安装 Atelier UI 和 Builder

Atelier UI 是 Hermes Dashboard 的用户 Plugin。当前仓库开发模式下，把 `plugin/atelier` 复制到当前 `HERMES_HOME` 的 plugins 目录：

```bash
cd /absolute/path/to/hermes-atelier
export ATELIER_PROJECT_ROOT="$PWD"
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

mkdir -p "$HERMES_HOME/plugins"
cp -R plugin/atelier "$HERMES_HOME/plugins/atelier"
hermes plugins enable atelier
```

上面的复制命令用于目标不存在的首次安装。已有 `atelier` Plugin 时先确认它是否属于其他工作，不要直接覆盖。

安装 Builder Profile，并使用 Hermes 原生模型选择器为它配置模型：

```bash
hermes -p default profile install \
  profiles/atelier-builder \
  --name atelier-builder \
  --yes \
  --force

hermes -p atelier-builder model
hermes -p atelier-builder config env-path
```

最后一个命令会打印 Builder 的 `.env` 路径。在该文件中加入：

```dotenv
API_SERVER_ENABLED=true
API_SERVER_PORT=19400
API_SERVER_KEY=<a-long-random-builder-key>
```

然后启动 Builder Gateway：

```bash
hermes -p atelier-builder gateway start
hermes -p atelier-builder gateway status
```

在启动 Dashboard 的同一个 shell 中提供 Builder 地址和相同的 Key：

```bash
export ATELIER_PROJECT_ROOT=/absolute/path/to/hermes-atelier
export ATELIER_BUILDER_URL=http://127.0.0.1:19400
export ATELIER_BUILDER_KEY_ENV=ATELIER_BUILDER_API_KEY
export ATELIER_BUILDER_API_KEY='<same-builder-key-as-profile-env>'

hermes dashboard
```

浏览器打开 Dashboard 后，左侧应出现 **Atelier**。如果没有，先运行 `hermes plugins list`，确认 Plugin 已安装且 enabled；如果 Design 报 401，确认 Dashboard shell 和 Builder `.env` 使用的是同一个 Key。

Drafter 和 Reviewer 暂时不要安装。它们是可选能力，不是完成第一个应用的前置条件。

### 阶段 2：用 Builder 对齐需求并导出 handoff

进入 **Atelier → Design**，直接输入原始业务需求。一个有效的首次需求应至少说明：

```text
我要做什么业务能力？
谁会通过 HTTP 调用它？
它可以访问哪些数据和工具？
哪些结论必须有证据，哪些情况必须回答不知道？
怎样算 Demo 验收通过？
明确不做什么？
```

示例：

```text
做一个内部客户反馈分诊应用。下游 CRM 通过 HTTP 发送反馈文本和可选订单号。
应用需要判断是否属于产品问题、交易问题或信息不足；只有订单号存在时才能查询交易数据；
不能虚构负责人、发布时间或退款状态，专家失败时要明确降级。
Demo 验收包含：纯产品问题、纯退款问题、跨域问题和信息不足四类。
本次不接真实 CRM、工单系统或生产数据库。
```

Builder 会在同一个 Hermes Session 中继续提问。你可以纠正目标、要求单 Profile 方案、调整权限边界，直到状态变成 `PLAN_READY`。

此时默认选择 **Export handoff**。你会得到：

- `.atelier/v2/designs/<design-id>/PLAN.md`；
- `.atelier/v2/designs/<design-id>/IMPLEMENTATION_HANDOFF.md`。

PLAN 解释“为什么这样设计”；handoff 告诉实现者“必须实现和验证什么”。`Generate with Hermes` 是可选 Drafter，不是下一步的默认按钮。

### 阶段 3：交给 Coding Agent 实现

把下面这类任务交给 Codex、Claude Code、Hermes 或人工实现者：

```text
请读取：
- .atelier/v2/designs/<design-id>/PLAN.md
- .atelier/v2/designs/<design-id>/IMPLEMENTATION_HANDOFF.md

在 apps/<pack-id>/ 实现一个通过 Hermes Atelier V2 schema 验证的 App Pack。
遵守 handoff 中的 Profile、工具、数据、权限、Session/Memory 和 HTTP 边界。
优先使用 Hermes 原生能力；不要把固定调用路线写成业务正确性的通用条件。
完成后运行 uv run atelier validate apps/<pack-id> 和相关测试，但不要自动安装、提交或发布。
```

Coding Agent 应生成 `app.yaml`、Profile Distributions、必要的 Skills/Plugins、Cases、README 和 INSTALL。单 Profile 完全合法；只有真实权限、数据、长期知识或隔离理由成立时才拆成多个 Profiles。

实现时可参考：

- 最小目录和单 Profile：`apps/single-profile-hello`；
- 按需专家调用：`apps/mini-voc`；
- Hermes 原生 delegation：`apps/delegation-note`。

### 阶段 4：验证并生成 App Pack release

```bash
uv run atelier validate apps/<pack-id>
uv run atelier cases apps/<pack-id>
uv run atelier release \
  apps/<pack-id> \
  /absolute/path/to/<pack-id>-release \
  --git-revision HEAD
```

这里的 `cases` 命令验证 Case 定义；真实模型执行发生在已配置实例上。release 要求 Pack 已提交且与所选 Git revision 一致，避免交付物来源含糊。

### 阶段 5：由 Consumer 用 Hermes 安装和运行

进入 release 目录，阅读它自己的 `INSTALL.md`。一般顺序是：

```bash
./app install --instance <instance-name>
./app configure --instance <instance-name> [模型、Provider、Key env 和端口]
./app start --instance <instance-name>
./app status --instance <instance-name>
```

wrapper 只提供便利配置。Consumer 可以继续用 `hermes -p <physical-profile> model` 或 `config set` 为不同 Profiles 选择不同模型；模型、端口和 Secret 不进入 `app.yaml`。

### 阶段 6：交付 HTTP 使用方式

交付给下游的最小信息只有：

- 入口 Base URL，例如 `http://127.0.0.1:19300`；
- Gateway Bearer Key 的安全传递方式；
- `/v1/chat/completions` 或 `/v1/responses`；
- 入口物理 Profile 名；
- Session ID 的使用约定；
- 已知业务限制。

curl 形态如下，具体值以 Pack 的 `INSTALL.md` 为准：

```bash
curl http://127.0.0.1:<entry-port>/v1/chat/completions \
  -H "Authorization: Bearer $HERMES_APP_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Session-Id: consumer-session-001' \
  -d '{"model":"<instance>--<entry-agent>","messages":[{"role":"user","content":"<business request>"}]}'
```

到这里 Core 路径已经结束。Dashboard 不必保持运行，下游也不需要理解 Design、Case、attestation 或 Trial。

## 怎样查看运行和协作证据

如果 Dashboard 使用的 `HERMES_HOME` 中已经安装了实例，进入 **Atelier → App Packs**：

1. 选择 Pack；
2. Overview 自动发现已安装实例；
3. Sessions & Evidence 自动列出最近入口 Sessions；
4. 选择 Session 查看当前可见的协作证据；
5. Delivery 查看安装命令、入口 HTTP、证据等级和已知限制。

`complete_trace` 只说明已观察到的 `profile_call` 有终态；`partial_trace` 表示可见事件不完整；没有 Trace 时，delegation、Kanban、MCP 或其他 Hermes 原生协作仍可能正常发生。Lens 是开发辅助，不是完整审计系统。

## 什么时候才需要 Assurance Lab

只有遇到下面的问题时，再进入 Assurance Lab：

- “当前安装资产和配置是否与 release 一致？”：configured runtime attestation；
- “Gateway 和 Hermes 当前是否真的可访问？”：live probe；
- “这组固定业务输入是否满足合同？”：Case runner；
- “候选实现是否比基线更好？”：Experiment 与可选 Reviewer；
- “本地更新失败后留下了什么证据？”：experimental update/rollback evidence。

创建普通 Demo 不要求完成这些层级。证据阶梯不是发布审批状态机。

## 常见卡点

### Dashboard 中没有 Atelier

- 运行 `hermes plugins list`；
- 确认 `<HERMES_HOME>/plugins/atelier/plugin.yaml` 存在；
- 运行 `hermes plugins enable atelier` 后重启 Dashboard。

### Design 无法开始

- 检查 `ATELIER_BUILDER_URL`；
- 检查 `ATELIER_BUILDER_KEY_ENV` 指向的环境变量是否存在；
- 检查 Builder Profile `.env` 的 `API_SERVER_ENABLED`、`API_SERVER_PORT` 和 `API_SERVER_KEY`；
- 运行 `hermes -p atelier-builder gateway status`；
- 确认 Builder 已通过 `hermes -p atelier-builder model` 配置可用模型。

### Pack 出现在源码中但 Dashboard 看不到

Dashboard 从 `ATELIER_PROJECT_ROOT/apps/` 自动发现 Pack。确认环境变量指向当前仓库，并确认文件位于 `apps/<pack-id>/app.yaml`。

### HTTP 能调用，但 Lens 没有 Trace

业务运行不依赖 Trace。单 Profile、delegation、Kanban、MCP 或没有安装 `profile_call` 的 Pack 都可能没有完整 Trace；不要为了 UI 可见性修改 Agent 的合理协作方式。

### release 失败并提示 Git revision 不一致

release 要求交付来源可追溯。先检查 `git status`，确认 Pack 改动已经由你审阅并提交，再选择相应 commit/tag；不要为了绕过检查伪造 revision。

## 下一步文档

- App Pack 字段与目录约束：[APP_PACK.md](APP_PACK.md)
- Builder、Drafter、Reviewer 边界：[BUILDER.md](BUILDER.md)
- 发布、配置、更新和卸载：[RELEASE.md](RELEASE.md)
- Cases 与 Experiments：[CASES_AND_EXPERIMENTS.md](CASES_AND_EXPERIMENTS.md)
- 安全保证与限制：[SECURITY.md](SECURITY.md)
