# Hermes Atelier V2.1 架构

## 组件与数据流

```text
Developer ── Builder Session ── PLAN + IMPLEMENTATION_HANDOFF
                                   │
                                   ├── selected Coding Agent / human
                                   └── optional Hermes Drafter
                                                │
                                                ▼
App Pack ── validate/release ── Consumer HERMES_HOME ── native Hermes Gateways
                                                             │
Consumer system ── OpenAI-compatible HTTP ── entry Profile ── chosen collaboration

Atelier Lens ── discovered Pack/instance/session + visible evidence
Assurance Lab ── configured attestation / live probe / Cases / Experiment / Reviewer
```

## 活动模块

- `app_pack.py`：V2 Manifest、定义快照、release filter 和 `app.lock`；
- `pack_app.py`：发布物内的薄 Hermes lifecycle proxy；
- `profile_call/`：完全独立的跨 Profile 协作 Plugin；
- `designs.py`：Hermes 原生多轮 Session、PLAN、Coding Agent handoff 与可选 Draft；
- `evaluation.py`：Case、Experiment、Trial、断言和 Reviewer；
- `studio_store.py`：仅保存开发证据，不保存应用 Runtime；
- `plugin_api_v2.py` 与 `index_v2.js`：App Pack 工作空间和可选 Assurance Lab。

V1 services、SQLite Store、旧 API/bundle、脚本及其内部状态机测试已退出 V2.1 源码和发布包；历史由 Git 保留。

## Design 权限切换

规划 Profile 使用 `/api/sessions/{id}/chat`，Hermes 原生 Session 是对话事实源。Profile config 禁用 terminal、file、code_execution、session_search、memory 和 delegation，避免规划轮写文件或污染其他 Design。

Builder ready 后默认导出 PLAN 与 handoff。`Generate with Hermes` 是单独的可选动作，调用独立 Drafter。Drafter 收到 PLAN、handoff 和目标 Draft 目录；`terminal.cwd` 不是文件系统沙箱，因此安全边界来自独立 Profile、最小凭据、人工选择和后端 Validator，而不是 cwd。失败不会进入正式应用或 Git。

## Run 与 Trace

通用多轮对话完全使用 Hermes 原生 Chat/Session。Atelier 不创建 Root Run、Span 或 Endpoint。`profile_call` 返回的 `source_session_id`、`target_session_id`、`target_hermes_run_id` 和 `call_id` 是真实关联；Trace Sink 只索引 started/completed/failed 事件，不从自然语言推断。

Trace HTTP 使用独立 Client 和极短 timeout；started 失败立即继续，completed 失败不改变结果。固定 Trace directory 按 `source_session_id` 哈希分文件，Case 不再改写共享 mapping。Lens 使用 `complete_trace | partial_trace | unobserved_collaboration_possible`；没有 Trace 不能被解释为没有协作。

## App Pack Runtime

安装时将逻辑 ID 物化为 `<instance>--<agent>`，每个调用方 Profile 的 `local/app-runtime.json` 保存：

- Pack 和实例 ID；
- 当前逻辑 Agent；
- self 与允许目标到物理 Profile/loopback URL 的映射；
- API Key 环境变量名；
- `allowed_calls`；
- 可选 Trace Sink。

映射不包含 Secret。configure 为每个目标生成独立 Gateway Key，调用方 `.env` 只获得 self 和允许目标的 Key。它能约束正常 `profile_call` 路径并减少凭据暴露，但同一 OS 用户下不是强进程隔离。每个物理 Profile 使用 Hermes 原生 Gateway；wrapper 不维护 PID、健康状态机或 Endpoint DB。

## Experiment

Experiment 属于 Assurance Lab。启动时使用 `configured_runtime_attestation` 冻结 Definition Snapshot、Pack revision、逐 Profile 配置记录、Case hash、Memory Policy 和候选 Git 元数据。`live_runtime_probe` 另行报告当前健康、Hermes version、capabilities 和 observable models；不能确认的身份标为 `unverified`。

通用断言仅支持 required/forbidden calls 与 must_contain/must_not_claim 字符串检查；业务复杂语义通过 Pack 自有 Evaluator 扩展，不进入 Atelier 核心。

## 核心不变量

1. Hermes 拥有 Profile、Gateway、Session、Run、Memory、模型、工具和进程；
2. Atelier 停止或 `.atelier` 删除不影响发布应用；
3. Agent 自主选择协作方式；Trace 和 Case 不规定路线；
4. `profile_call` 不选择专家、顺序、并行、聚合、重试或降级；
5. Builder 默认导出 handoff，Drafter 必须显式选择；
6. Assurance Lab 不阻塞普通 Demo，Reviewer 不是 Core 依赖；
7. 候选修改通过 Git，不通过 Atelier Patch Store；
8. Release 不包含 Secret、Memory、Sessions、Trace、PID 或本地映射；
9. Atelier 核心没有示例业务特判；
10. `profile_call` 独立且可由未来 Hermes 原生能力替换。
