# App Pack 合同

## 目的

App Pack 是可复制、可放入 Git、可独立验证和安装的 Hermes 应用目录；单 Profile 与多 Profile 都是正常形态。它补充单个 Distribution 无法表达的应用级分组：逻辑 Agent、唯一公开入口、调用声明、公开协议、状态声明、Cases 和 Contracts。

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

`atelier release` 另外生成可执行的 `app` 和不可变的 `app.lock`。`app.lock` 固化所有交付文件、Profile、Case、Contract 的摘要，source/release revision、Manifest、完整 Cases 和可验证 source provenance，不包含 Secret。

## Manifest

```yaml
schema_version: 2
id: sample-app
version: 2.1.0
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
- Schema V2 使用 Pydantic `extra="forbid"`，但不递归审查自然语言或嵌套配置是否包含设计哲学关键词；
- Case 与 Contract 必须存在、不能重复且不能逃逸 Pack 根目录；Case 必须通过完整 schema 与 Memory Policy 校验，Contract 必须是 JSON object；
- `public_api.output_contract` 必须是 Pack 内相对路径，并已列入 `contracts`。

## 字段保证与状态声明

字段含义必须区分四层：

- 机器保证：schema、路径、唯一 entry、Distribution 存在性、release filter 和 lock hash；
- Pack 声明：`state_policy`、`state_compatibility`、`allowed_calls`、`collaboration`；
- Consumer 责任：网络/进程隔离、入口 ingress、模型选择、Secret、状态迁移和生产部署；
- Hermes 限制：Profile 全局 Memory、同 OS 用户文件权限、Plugin/Gateway 的实际能力。

- `stateless`：应用定义不依赖跨请求状态；Hermes 仍可能保留平台级运行记录。
- `session_only`：同一 Hermes Session 内允许上下文延续，不声明跨 Session 长期状态。
- `caller_scoped`：应用只在 Consumer 显式选择的稳定 scope 下访问长期状态。Hermes 0.19.0 的全局 Profile Memory 不按 Session-Key 隔离；应用必须使用自己的 Profile-local scoped store 或由 Consumer 为 caller 隔离物理实例。Project Defense 选择前者。

更新兼容提示与状态所有权分离：

- `preserve`：定义预期兼容既有状态；
- `review_required`：更新前应由 Consumer 评估既有 Memory/Session；
- `reset_recommended`：建议新作用域或人工清理，但 wrapper 不执行重置。

## 逻辑身份与物理身份

Pack 永远只引用 `host`、`expert` 之类的逻辑 ID。安装时 Consumer 选择 `instance`，物理 Profile 为 `<instance>--<logical-id>`。例如 `support-demo--host`。

每个 Profile 的 `local/app-runtime.json` 只保存 self 与允许目标的物理 Profile、loopback URL、独立 API Key 环境变量名和该来源的 `allowed_calls`。它不保存 Key。`.env` 只注入该调用方真正需要的目标 Key。这个边界是 `profile_call` Tool Policy 与凭据最小化，不是同一 OS 用户下的强授权隔离。

## 发布过滤

Release 递归排除 `.env` 及私有变体、`MEMORY.md`、`USER.md`、`local/`、Sessions、Logs、Trace、PID、bytecode、Atelier 数据和旧 `app.lock`，保留只有占位符的 `.env.example`。Pack 禁止 symlink；发布物再次扫描私钥以及常见 Cloud/API credential 赋值形状。Release 先在同一父目录的临时 staging 中完成复制、注入、验证、Secret 扫描和 lock 生成，全部成功后才原子改名为目标目录；失败不会留下半成品目标。Definition Snapshot 哈希注入 Plugin 和生成 wrapper 后的每个交付文件。若使用 `profile_call`，Release 只把该 Plugin 注入有出边的调用方 Distribution。

Git checkout 中的 Pack 必须先提交；Release 将 commit/tag 解析为完整 commit，并拒绝 Pack 路径的 tracked/untracked 漂移。非 Git 目录使用完整 source content SHA-256 provenance，不能写任意 revision 字符串。

## 验证

```bash
uv run atelier validate apps/mini-voc
uv run atelier cases apps/mini-voc
uv run atelier release apps/mini-voc /tmp/mini-voc-release --git-revision HEAD
```

Validator 只证明结构和发布边界，不证明 SOUL、模型行为或生产可用性。证据等级为 `packed`、`installed`、`configured`、`runtime_attested`、`live_probed`、`cases_passed`、`fresh_verified`；层级可缺失，不能把 `packed` 称为 validated release。

`./app attest` 生成 `configured_runtime_attestation`，校验 lock、安装资产、映射和逐 Profile 配置记录。`./app live-probe` 通过各 Profile Gateway 检查 health、Hermes version、capabilities 与 observable models；无法从 Hermes API 确认的 Profile identity 标为 `unverified`。`./app cases` 使用固定实例 Trace 目录，不修改共享 mapping。真实模型结果仍需人工审阅。

wrapper 只提供统一默认模型的便利配置。Consumer 可以用 Hermes 原生命令逐 Profile 覆盖，Manifest 不新增模型字段；configured attestation 标明实际 config hash 是否仍匹配 wrapper 记录，live probe 报告当前可观察模型。
