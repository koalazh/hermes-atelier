# V2 验证证据与已知限制

验证日期为 2026-07-25，目标环境是本地已安装的 Hermes Agent 0.19.0。Hermes 核心只读使用，没有修改或提交上游代码。

## 当前 Hermes 能力审计

源码与真实探针确认 Hermes 提供 Profile Distribution install/update、Profile config、原生 Gateway 生命周期、`/api/sessions` 多轮 Chat、OpenAI 兼容 Chat/Responses、异步 `/v1/runs` 与 SSE、Plugin context 和 Memory scope。

同时确认当前 multiplex Gateway 的 Plugin Manager 为进程级单例，只从默认 Hermes Home 发现一次 Plugins，不能安全承载示例的 Profile 私有业务 Plugins。因此 V2 release 为每个物理 Profile 使用一个显式 loopback Gateway；该取舍应在 Hermes 提供 Profile-scoped Plugin registry 后重新评估。

## 确定性验证

V2 自动化覆盖：

- Manifest 逻辑身份、唯一入口、权限、路径、Workflow key 和运行态过滤；
- Definition Snapshot、release、`app.lock`、smoke Case 和 `profile_call` 注入；
- wrapper install/configure/start/stop/status/update，以及新 smoke 失败后的旧映射回滚；
- 独立 `profile_call` 的 allowlist、真实目标元数据、Memory scope、目标错误与 Trace 降级；
- Builder 同一 Hermes Session 多轮对话、状态转换、独立 Drafter 和 V2 Draft 验证；
- Case/Memory Policy、Experiment 冻结、Trial/Trace/断言、反馈与整个 Experiment Review；
- V2 API、CLI、Dashboard bundle 和 Studio 文件证据存储。

全量 pytest、Ruff、Dashboard JavaScript 语法和 Python sdist/wheel 构建是最终交付门禁；精确结果在完成时更新，不把测试数量解释为生产质量指标。

## Mini VOC fresh runtime

在全新、与开发 Studio 分离的 `HERMES_HOME` 中发布并安装 Mini VOC，启动三个原生 Profile Gateways。入口使用普通外部 Session `external-consumer-session-002`，真实产生两次 `profile_call`：

- Product 目标物理 Profile 为 `mini-voc-test--product`，目标 Session `pc_34b…`，Hermes Run `run_a0d704…`，并执行 `voc_product_lookup`；
- Transaction 目标物理 Profile 为 `mini-voc-test--transaction`，目标 Session `pc_c9ff…`，Hermes Run `run_d506…`，并执行 `voc_transaction_lookup`。

最终回答引用模拟记录 `PRD-LOGIN-17` 与 `ORD-1001`，且明确说明不是生产数据。验证期间 Atelier Dashboard 未运行，fresh runtime 不含 `.atelier`，证明应用主路径不依赖 Studio。随后停止并清理了本任务启动的 Gateways、Profile 运行态和 launchd 条目。

首次真实调用使用了错误模型名并诚实返回 Provider 400；改为用户指定的有效模型标识后成功。这证明失败没有被 wrapper 或 Plugin伪装为业务结果。

## Builder 与 Drafter 真实会话

真实 Hermes Builder Session `atelier_design_7410564f…` 完成两轮对话：第一轮为 `NEEDS_INPUT`，开发者补充后进入 `PLAN_READY`。显式 Drafter Run `run_dfecdb…` 生成并通过验证的 V2 Pack，包含 `app.yaml`、Case 和 Profile Distribution。

验证还发现并修正了三个真实边界误解：`/v1/runs` 的 `session_id` 不会载入 Chat 历史；规划 Profile 不应拥有写工具或 Session 搜索；Drafter 必须收到精确 V2 schema 并由后端严格验证。最终实现改用 `/api/sessions/{id}/chat`、分离 Builder/Drafter 权限并保留严格 Validator。

相关 Builder/Drafter Gateways 在验证后已停止并清理。

## Project Defense fresh runtime

最终门禁将记录全新安装下同一外部 Hermes Session 的多轮答辩、真实 Source/Architecture/Coach 调用证据以及无来源 p99 数字的拒绝结果。若外部模型随机性导致 Case 断言不稳定，只记录实际观察，不把一次输出改写为确定性能力。

## 已知限制

- 真实模型输出具有随机性，smoke 只证明协议和资产链路可执行；
- Trace Sink 是可选开发观测，不是生产审计；缺少 Trace 不能独立证明没有调用；
- update 是多条 Hermes/文件/网络操作的 best-effort 回滚，不是事务部署；
- 当前每 Profile 一个 Gateway 是 Hermes Plugin 隔离限制下的取舍；
- V1 compatibility 模块仍在仓库中作为回归证据，但不在 V2 活动 manifest、CLI 或 Dashboard 路径；
- Atelier 不提供多租户、企业 RBAC、远程 Registry、生产 Agent Mesh、蓝绿发布或自动优化。
