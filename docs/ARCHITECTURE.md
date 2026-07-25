# Hermes Atelier V2 架构

## 组件与数据流

```text
Developer ── native Hermes Session ── Builder Profile (read-only planning)
                    │
                    └── explicit Generate Draft ── Drafter Profile (scoped write)

Consumer ── OpenAI-compatible HTTP ── public entry Profile
                                         │
                                         └── profile_call ── internal Profile(s)
                                                │
                                                └── optional Trace Sink ── Atelier

Case + Pack revision + model fingerprint + Memory policy
                    └── Experiment ── Trial(s) ── optional Reviewer Profile

App Pack release ── fresh HERMES_HOME ── Hermes native Profiles/Gateways
```

## 活动模块

- `app_pack.py`：V2 Manifest、定义快照、release filter 和 `app.lock`；
- `pack_app.py`：发布物内的薄 Hermes lifecycle proxy；
- `profile_call/`：完全独立的跨 Profile 协作 Plugin；
- `designs.py`：Hermes 原生多轮 Session、PLAN 与显式 Draft；
- `evaluation.py`：Case、Experiment、Trial、断言和 Reviewer；
- `studio_store.py`：仅保存开发证据，不保存应用 Runtime；
- `plugin_api_v2.py` 与 `index_v2.js`：V2 Dashboard 活动入口。

V1 `services/`、SQLite Store、旧 Dashboard bundle 和旧脚本只用于迁移期回归，不被 V2 manifest/CLI 引用。

## Design 权限切换

规划 Profile 使用 `/api/sessions/{id}/chat`，Hermes 原生 Session 是对话事实源。Profile config 禁用 terminal、file、code_execution、session_search、memory 和 delegation，避免规划轮写文件或污染其他 Design。

`Generate Draft` 是单独 API 动作，调用独立安装但同属 Builder 能力的 Drafter Profile。Drafter 只收到批准的 PLAN 和一个精确 Draft 目录；后端随后以 AppPack Validator 验证恰好一个 `app.yaml`。Draft 失败不会进入正式应用或 Git。

## Run 与 Trace

通用多轮对话完全使用 Hermes 原生 Chat/Session。Atelier 不创建 Root Run、Span 或 Endpoint。`profile_call` 返回的 `source_session_id`、`target_session_id`、`target_hermes_run_id` 和 `call_id` 是真实关联；Trace Sink 只索引 started/completed/failed 事件，不从自然语言推断。

Trace 写入失败时 `trace_degraded=true`，真实业务结果仍返回。没有 Trace 不能被解释为“没有调用”，除非目标 Session/工具历史也提供相同证据。

## App Pack Runtime

安装时将逻辑 ID 物化为 `<instance>--<agent>`，每个调用方 Profile 的 `local/app-runtime.json` 保存：

- Pack 和实例 ID；
- 当前逻辑 Agent；
- 逻辑 Agent 到物理 Profile/loopback URL 的映射；
- API Key 环境变量名；
- `allowed_calls`；
- 可选 Trace Sink。

映射不包含 Secret。每个物理 Profile 使用 Hermes 原生 Gateway；wrapper 不维护 PID、健康状态机或 Endpoint DB。

## Experiment

Experiment 启动时冻结 Definition Snapshot、Pack revision、模型/Provider 指纹、Case hash、Memory Policy 和候选 Git 元数据。Trial 绑定真实 entry Session/Run、输出、Trace 和断言。运行期间 Case hash 变化会使 Experiment 失败，避免候选同时修改评价标准。

通用断言仅支持 required/forbidden calls 与 must_contain/must_not_claim 字符串检查；业务复杂语义通过 Pack 自有 Evaluator 扩展，不进入 Atelier 核心。

## 核心不变量

1. Hermes 拥有 Profile、Gateway、Session、Run、Memory 和进程；
2. Atelier 停止或 `.atelier` 删除不影响发布应用；
3. `allowed_calls` 是权限边界，不是路由或 Workflow；
4. `profile_call` 不选择专家、顺序、并行、聚合、重试或降级；
5. Builder 规划无写权限，Draft 必须显式触发；
6. Reviewer 只分析完整 Experiment，不声称已优化；
7. 候选修改通过 Git，不通过 Atelier Patch Store；
8. Release 不包含 Secret、Memory、Sessions、Trace、PID 或本地映射；
9. Atelier 核心没有示例业务特判；
10. Hermes 提供可靠等价能力后删除 Atelier 接缝。
