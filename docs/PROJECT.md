# Hermes Atelier V2 项目说明

## 最终解决的问题

Hermes 已经提供 Profile、Session、Run、Memory、Gateway、Plugins、Kanban 和 Dashboard。Atelier 只补足多 Profile 应用的开发闭环：多轮设计、真实协作观察、可复现 Case/Experiment，以及独立 App Pack 交付。

Atelier 的价值不是“让应用运行”，而是帮助开发者回答：目标是否对齐、Profile 边界是否有理由、真实调用发生了什么、不同定义和 Memory 条件是否可比较、交付物能否脱离 Studio 安装。

## 为什么不是 AgentHub

AgentHub 需要通用 Registry、远程 Agent 发现、租户/权限模型、调度、服务治理和生产控制面。Atelier 不拥有这些。应用就是一组原生 Hermes Profile Distributions 和业务资产；远程部署与组合由 Consumer 自己的 Web、后端、Workflow 或 Agent 完成。

## 为什么不参与发布应用 Runtime

V1 让 `atelier_call` 依赖 Atelier Run/SQLite，并由 Endpoint Registry、端口分配、PID 和 Dashboard 后台任务管理 Profile。结果是停止 Studio 会改变应用能力，且与 Hermes 原生生命周期重复。

V2 发布应用只依赖 Hermes 和 Pack。Atelier Trace 是可选观测，故障或删除不能改变业务调用结果。

## 为什么需要 App Pack

单个 Profile Distribution 不足以表达多 Profile 应用的逻辑 Agent、权限边界、公开入口、状态策略、Cases 和 Contracts。App Pack 是克制的版本化目录约定，不是包管理平台，也不包含运行态。

## 为什么 profile_call 独立于 Studio

跨 Profile HTTP 是应用协作能力，不是开发 UI 能力。`profile_call` 只做逻辑目标解析、权限校验、目标 Hermes Run 和元数据返回；它不导入 Atelier、不读 SQLite、不解析 Atelier Session，也不负责路由、并行、聚合、业务重试或降级。

## 所有权

| 组件 | 拥有 |
| --- | --- |
| Hermes | Profile、Gateway、Session、Run、Memory、Plugins、模型、工具与进程生命周期 |
| Atelier Studio | Design/PLAN/Draft 开发体验、真实 Trace 索引、Case/Experiment、Release 验证 |
| App Pack | 逻辑 Agent、Distributions、权限边界、Public API、状态策略、Cases、Contracts |
| Consumer | 实例名、Secret、端口、ingress、运行映射、用户状态、部署和业务组合 |

## V1 被证明错误的抽象

- Atelier Endpoint/PID Registry 作为运行事实源；
- `task_id == session_id` 的 Atelier 专属调用协议；
- 一次性 Build 和弱化的一次性 Playground；
- 单个 Run Review 后直接 Proposal/Replay；
- Dashboard 后台任务作为隐式 Runtime；
- 统一模型注入和所有业务 Profile 强制安装 Atelier Plugin；
- 对当前工作树直接 `git apply`。

旧代码保留为迁移期回归证据，不再由 V2 Plugin manifest、CLI 或 Dashboard 活动入口引用。

## 应贡献给 Hermes 上游的能力

- Profile-scoped Plugin registry，使 multiplex 能安全加载不同业务 Plugins；
- 多 Profile 应用分组与公开/内部端点语义；
- 原生跨 Profile 调用及标准 Trace Context；
- Session/Run 的 Experiment 元数据挂接；
- Distribution 更新后的标准 smoke hook。

## Kill / Pivot 条件

- Hermes 原生覆盖 Design、Trace、Experiment 或 App Group，Atelier 应删除重复模块；
- 第三个应用迫使核心增加业务特判，停止扩张并回退到应用资产；
- Builder Draft 长期不能通过 Pack Validator，收缩为 PLAN/Skill；
- Trace 索引被当成业务调用前置条件，立即拆除该依赖；
- 开发者直接使用 Hermes 和 Git 更高效，收缩为 App Pack Validator/Release 工具；
- 维护成本高于调试和交付价值，优先贡献通用能力到 Hermes 上游。
