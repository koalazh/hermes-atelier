# V2 Trace 数据模型

## Hermes 是运行事实源

- Hermes Session：单个 Profile 的对话身份和 transcript；
- Hermes Run：单个 Profile 的一次异步执行；
- `profile_call`：一次来源 Profile 到目标 Profile 的真实 HTTP 协作；
- Atelier Trace：对 `profile_call` 事件的可选、脱敏、best-effort 开发索引。

V2 没有 Atelier Root Run、Span Runtime 或合并 transcript。Studio 删除后，Hermes Session/Run 和发布应用仍然存在。

## 关联字段

每次 `profile_call` 生成随机 `call_id` 和独立 `target_session_id=pc_<call-id>`，并保留：

- `source` / `target` 逻辑 Agent；
- `source_session_id`；
- `target_session_id`；
- `target_hermes_run_id`；
- Hermes Plugin context 提供的可选 `task_id`；
- started/completed/failed 状态、脱敏结果或错误。

这些字段来自运行映射和真实 Hermes 响应。自然语言中声称的 Profile、Session 或 Run ID 不是可信身份。

## 事件

```text
profile_call.started
profile_call.completed
profile_call.failed
```

started 在目标 dispatch 前尝试上报；completed/failed 在目标真实终态后尝试上报。同一 `call_id` 关联一对事件。Studio 只保存必要索引，不复制目标完整 transcript、Memory、环境变量或工作目录。

## Experiment 绑定

Experiment Trial 创建唯一来源 Session。断言只读取该 `source_session_id` 的 Trace，避免跨 Trial 污染。Trial 同时保存入口 Hermes Run ID、终态和输出；Trace 只是协作证据的一部分。

`clean` 与 `session_only` 不传长期 scope；`retained` 将独立 `memory_scope` 传给入口 Run，并要求有状态下游继续显式传递。`profile_call` 只在目标 Session ID 中放截断 SHA-256 派生 ID，不直接放原始 scope；这只是标识符最小化，不是针对低熵 scope 的加密保护。Session ID、原始 scope 与应用的 Profile-local scoped state 不能混为一谈。

## 降级与证据边界

dispatch 前无法解析映射、授权目标或读取 Secret 时失败关闭。目标已经完成但 Trace Sink 不可用时，`profile_call` 返回真实业务结果并设置 `trace_degraded=true`。

因此：

- completed Trace 可证明该目标调用完成；
- failed Trace 可证明尝试及其失败，但不能证明业务状态；
- 没有 Trace 不能单独证明没有调用；
- Trace 不是生产审计、分布式追踪或计费系统；
- 模型输出引用的事实仍需检查目标工具证据。

## 脱敏与保留

Trace 入口和 Studio Store 对 Authorization、常见 Secret assignment 和 Key 形状执行脱敏。`.atelier/v2/traces` 是可删除开发证据，默认不进入 Git 或 App Pack。需要长期审计时应使用 Consumer 自己的受控观测设施，而不是扩大 Atelier 所有权。
