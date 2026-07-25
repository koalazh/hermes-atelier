# profile_call 协作边界

## 定位

`profile_call` 是随 App Pack 发布的独立 Hermes Plugin，不是 Atelier Studio 的子模块。发布应用在 Atelier 停止、不可达或被删除后仍可调用内部 Profile。

它负责：

- 从当前 Profile 的 `local/app-runtime.json` 获取逻辑身份和映射；
- 校验来源到目标的 `allowed_calls`；
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

这些字段来自实际 Hermes 调用，不能由自然语言或 Atelier 数据库推断。Plugin handler 的错误结果使用 `ok: false` 和 `error_type: profile_call_failed`；调用方可据此诚实说明证据不可用，但不得把失败解释为业务状态。

## Runtime Mapping

```json
{
  "schema_version": 1,
  "pack_id": "mini-voc",
  "pack_version": "2.0.0",
  "instance": "support-demo",
  "current_agent": "dispatcher",
  "agents": {
    "product": {
      "profile": "support-demo--product",
      "base_url": "http://127.0.0.1:19301",
      "api_key_env": "HERMES_APP_API_KEY"
    }
  },
  "allowed_calls": {"dispatcher": ["product", "transaction"]}
}
```

Wrapper 为每个物理 Profile 生成完整映射，但校验始终以 `current_agent` 的 allowlist 为准。API Key 只从目标进程环境读取。

## Session 与 Memory

来源 Session ID 只用于关联；clean 调用创建 `pc_<call-id>` 形式的独立 Hermes Session。显式 `memory_scope` 会被 SHA-256 后截取为派生 scope ID，目标 Session 为 `pcms_<scope-id>_<call-id>`；原始 scope 不写入 Session ID 或 Trace。该 hash 用于标识符最小化，不应被当作低熵 scope 的加密保护。`/v1/runs` 的 `session_id` 是调用身份，不等同于 Hermes Chat 的多轮消息载入。

只有显式 `memory_scope` 才发送 `X-Hermes-Session-Key` 并生成 scope ID。该 Header 不会自动写 Memory；Hermes 0.19.0 的 `MEMORY.md` / `USER.md` 仍是物理 Profile 全局文件。需要 caller isolation 的应用应让自己的状态工具从 `pcms_` Session 读取 scope ID，并把状态保存在 Profile `local/` 下；只有工具成功后才能声称已经保存。Project Defense Coach 使用这一模式并禁用 Hermes 全局 Memory。

## Trace 失败语义

Trace 是 best-effort 开发观测：

- dispatch 前映射缺失、目标越权、Secret 缺失或目标 HTTP 失败：业务调用失败；
- 目标已成功但 Trace Sink 失败：返回真实结果并设置 `trace_degraded: true`；
- 没有 Trace 不能单独证明“没有调用”，应结合目标 Hermes Session/Run 证据。

Trace 不应保存 Secret；Studio 接收端还会执行脱敏。

## 当前部署取舍

当前 Hermes multiplex Gateway 的 Plugin Manager 是进程级单例，不能隔离 Profile 私有业务 Plugins。示例因此为每个物理 Profile 使用一个 loopback Gateway。若 Hermes 上游提供 Profile-scoped Plugin registry，Pack wrapper 应收缩并优先使用原生多 Profile 托管。
