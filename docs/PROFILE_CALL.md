# profile_call 协作边界

## 定位

`profile_call` 是随 App Pack 发布的独立 Hermes Plugin，不是 Atelier Studio 的子模块。发布应用在 Atelier 停止、不可达或被删除后仍可调用内部 Profile。

它负责：

- 从当前 Profile 的 `local/app-runtime.json` 获取逻辑身份和映射；
- 按 `allowed_calls` Tool Policy 校验来源到目标；
- 以目标 Profile 的 Gateway API Key 调用 Hermes `/v1/runs`；
- 为目标创建独立 Session，按 SSE 等待真实终态；
- 返回目标逻辑 ID、物理 Profile、Session、Hermes Run 和 `call_id`；
- 可选地向 Trace Sink 上报 started/completed/failed 事件。

它不负责选择专家、编排顺序、并行、聚合、裁判、业务重试、备用路由、结果解释或长期 Memory 策略。以上由调用 Agent 的 SOUL、Skill 和模型自主决定。

## 工具输入

```json
{
  "target": "product",
  "task": "核查登录验证码是否有已知记录，并区分模拟数据与生产事实。",
  "memory_scope": "optional-consumer-owned-scope",
  "timeout_seconds": 120
}
```

`target` 和 `task` 必填；`memory_scope` 只有应用明确需要 caller-scoped 长期状态时才使用；超时范围是 1 到 900 秒。

## 成功结果

```json
{
  "ok": true,
  "target": "product",
  "target_profile": "support-demo--product",
  "result": "...",
  "source_session_id": "consumer-session-001",
  "target_session_id": "pc_<call-id>",
  "target_hermes_run_id": "run_<id>",
  "call_id": "<id>",
  "trace_degraded": false
}
```

这些字段来自实际 Hermes 调用，不能由自然语言或 Atelier 数据库推断。Plugin handler 的错误结果使用 `ok: false` 和 `error_type: profile_call_failed`；异常发生在子 Run 创建后时还可能带 `stop_status`。

## Runtime Mapping

```json
{
  "schema_version": 1,
  "pack_id": "mini-voc",
  "pack_version": "2.1.0",
  "instance": "support-demo",
  "current_agent": "dispatcher",
  "agents": {
    "product": {
      "profile": "support-demo--product",
      "base_url": "http://127.0.0.1:19301",
      "api_key_env": "HERMES_APP_API_KEY__PRODUCT"
    }
  },
  "allowed_calls": {"dispatcher": ["product", "transaction"]}
}
```

Wrapper 为每个 Profile 只生成 self 与允许目标映射，并为每个目标生成独立 Key；调用方 `.env` 只获得所需目标 Key。API Key 只从目标声明的环境变量读取。这个设计约束正常工具路径并减少凭据暴露，但 `terminal.cwd` 不是沙箱，同一 OS 用户也不是进程隔离，因此不能把 `allowed_calls` 宣称为强 RBAC。

## Session 与 Memory

来源 Session ID 只用于关联；不带 scope 的调用创建 `pc_<call-id>` 形式的新 Hermes Session，但这不保证目标 Profile 的 Memory 或 local state 为空。显式 `memory_scope` 会被 SHA-256 后截取为派生 scope ID，目标 Session 为 `pcms_<scope-id>_<call-id>`；原始 scope 不写入 Session ID 或 Trace。该 hash 用于标识符最小化，不应被当作低熵 scope 的加密保护。

只有显式 `memory_scope` 才发送 `X-Hermes-Session-Key` 并生成 scope ID。该 Header 不会自动写 Memory；Hermes 0.19.0 的 `MEMORY.md` / `USER.md` 仍是物理 Profile 全局文件。需要 caller isolation 的应用应让自己的状态工具从 `pcms_` Session 读取 scope ID，并把状态保存在 Profile `local/` 下；只有工具成功后才能声称已经保存。Project Defense Coach 使用这一模式并禁用 Hermes 全局 Memory。

## Trace 失败语义

Trace 是 best-effort 开发观测，并与业务 HTTP 解耦：

- dispatch 前映射缺失、目标越权、Secret 缺失或目标 HTTP 失败：业务调用失败；
- Trace HTTP 使用独立 Client 和极短 timeout；started 失败立即 dispatch，completed 失败仍返回真实结果；
- 文件 Trace 按 source Session 哈希分文件，写入失败只设置 `trace_degraded: true`；
- timeout、caller cancellation、SSE 断开、网络或解析失败后 best-effort 调用 Hermes stop；
- `stop_requested` 只说明 Hermes 接受停止请求；无法确认终态时必须写 `stop_unknown`；
- Lens 区分 `complete_trace | partial_trace | unobserved_collaboration_possible`。

Trace 不应保存 Secret；Studio 接收端还会执行脱敏。

## 当前部署取舍

当前 Hermes multiplex Gateway 的 Plugin Manager 是进程级单例，不能隔离 Profile 私有业务 Plugins。示例因此为每个物理 Profile 使用一个 loopback Gateway。若 Hermes 上游提供 Profile-scoped Plugin registry，Pack wrapper 应收缩并优先使用原生多 Profile 托管。
