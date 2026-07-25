# App Pack 合同

## 目的

App Pack 是可复制、可放入 Git、可独立验证和安装的 Hermes 多 Profile 应用目录。它补充单个 Hermes Profile Distribution 无法表达的应用级信息：逻辑 Agent、唯一公开入口、调用权限、公开协议、状态策略、Cases 和 Contracts。

它不是包管理平台、远程 Agent Registry、Workflow DSL、部署控制面或运行时数据库。

## 目录

```text
my-app/
├── app.yaml
├── profiles/<logical-agent>/
│   ├── distribution.yaml
│   ├── SOUL.md
│   ├── config.yaml
│   ├── skills/
│   └── plugins/
├── cases/
├── contracts/
├── README.md
├── INSTALL.md
├── CHANGELOG.md
└── .env.example
```

`atelier release` 另外生成可执行的 `app` 和不可变的 `app.lock`。`app.lock` 固化 Profile 文件摘要、Pack revision、Manifest 和首个可用 smoke Case 输入，不包含 Secret。

## Manifest

```yaml
schema_version: 2
id: sample-app
version: 2.0.0
entry: host
agents:
  host:
    distribution: profiles/host
    exposure: public
  expert:
    distribution: profiles/expert
    exposure: internal
allowed_calls:
  host: [expert]
collaboration: [profile_call]
public_api:
  protocol: openai
  endpoints: [/v1/responses, /v1/chat/completions]
state_policy: session_only
state_compatibility: preserve
cases: [cases/smoke.yaml]
contracts: []
```

约束：

- `id` 使用小写 kebab-case；逻辑 Agent ID 使用小写字母、数字、`-` 或 `_`；
- `entry` 必须是唯一 `public` Agent，其他 Agent 必须为 `internal`；
- Distribution 路径必须是 Pack 内的相对目录，并包含 `distribution.yaml`；
- `allowed_calls` 的来源和目标必须已声明，不能自调用或重复；
- `public_api` 当前只接受 Hermes 原生 OpenAI 兼容端点；
- Manifest 任意深度都禁止 Workflow 关键词；
- Case 与 Contract 必须存在且不能逃逸 Pack 根目录。

## 状态策略

- `stateless`：应用定义不依赖跨请求状态；Hermes 仍可能保留平台级运行记录。
- `session_only`：同一 Hermes Session 内允许上下文延续，不声明跨 Session 长期状态。
- `caller_scoped`：应用只在 Consumer 显式选择的稳定 scope 下访问长期状态。Hermes 0.19.0 的全局 Profile Memory 不按 Session-Key 隔离；应用必须使用自己的 Profile-local scoped store 或由 Consumer 为 caller 隔离物理实例。Project Defense 选择前者。

更新兼容提示与状态所有权分离：

- `preserve`：定义预期兼容既有状态；
- `review_required`：更新前应由 Consumer 评估既有 Memory/Session；
- `reset_recommended`：建议新作用域或人工清理，但 wrapper 不执行重置。

## 逻辑身份与物理身份

Pack 永远只引用 `host`、`expert` 之类的逻辑 ID。安装时 Consumer 选择 `instance`，物理 Profile 为 `<instance>--<logical-id>`。例如 `support-demo--host`。

每个 Profile 的 `local/app-runtime.json` 保存逻辑到物理 Profile、loopback URL、API Key 环境变量名和该来源的 `allowed_calls`。它不保存 API Key。运行映射属于 Consumer 运行态，不进入 release。

## 发布过滤

Release 递归排除 `.env`、`local/`、Memory、Sessions、Logs、Trace、PID、Atelier 数据和旧 `app.lock`。定义快照只哈希可发布文件。若使用 `profile_call`，Release 只把该 Plugin 注入有出边的调用方 Distribution。

## 验证

```bash
uv run atelier validate apps/mini-voc
uv run atelier cases apps/mini-voc
uv run atelier release apps/mini-voc /tmp/mini-voc-release --git-revision HEAD
```

Validator 验证结构和边界，不证明 SOUL 质量、模型行为或生产可用性。真实行为需要 fresh `HERMES_HOME` 安装和 Case/Experiment 证据。
