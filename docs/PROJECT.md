# Hermes Atelier V1 项目说明

## 项目立意

Hermes Atelier 为开发者提供一个克制的本地空间：把业务意图转换成完整 Hermes Agents，观察真实跨 Profile 协作，从证据诊断问题，并且只在明确批准后应用可审查修改。

它是 Atelier 而不是 AgentHub，因为它不拥有通用 Registry、调度器、远程 Mesh、租户模型或生产控制面。一个应用仍然只是仓库中的一组原生 Hermes Profile Distributions，执行环境始终是 Hermes。

## 为什么 Builder 是 Skill 驱动的 Hermes Profile

意图对齐、边界发现和 Profile 设计需要 Agent 判断。若由 Python 模板完成，这套模板会逐渐变成固定角色目录和 Workflow 生成器。Builder 默认单 Profile，并为每次拆分记录具体隔离理由；它本身也使用 Hermes 原生 SOUL、Skill、Memory、Session 与工具。

## 为什么仍需要统一 Web UI

开发闭环需要一个位置完成草稿批准、真实父子 Runs 查看、Trace 证据比较、候选 Diff 审查与同场景 Replay。Atelier Tab 只增加这些开发操作。Hermes Dashboard 继续拥有 Profile 管理、Config、密钥、Skills、MCP、Sessions、Chat、日志与 Gateway 管理。

## 为什么只有一个 atelier_call

任意 `curl` 无法建立可信的调用者身份以及父子 Session/Run 关系。`atelier_call` 校验当前应用白名单并记录真实调用边界，但不会替 Agent 选择专家、决定顺序、判断证据、聚合结果或执行业务降级。

## 与 Hermes Self-Evolution 的边界

Hermes Self-Evolution 与 Atelier Review 是两条不同边界。Reviewer 只读一次冻结、收敛范围的证据包，不能修改应用、Memory、场景、评价标准或正式 Profiles。Builder 可以生成路径受限的候选 Patch，但只有后端批准状态才能应用，且改进结论必须通过原场景 Replay 验证。

## 稳定边界与 Agent 自主空间

Atelier 控制 Profile 身份、应用成员、调用白名单、loopback 端点、运行凭据、Session/Run 关联、Trace、文件范围、明确批准、进程健康与失败状态。

Agent 控制业务理解、调查、任务拆解、是否委派、委派对象与顺序、工具使用、证据充分性和最终输出。目标、对齐方案、Profile 边界、验收场景、版本、Trace、Review 与 Proposal 可以外部化；业务步骤、路由谓词、fan-out、aggregate、judge 和业务重试不能进入 Atelier 核心或 `app.yaml`。

## 明确非目标

V1 不提供 multiplex Gateway、Workflow DSL/编辑器、通用 Agent Registry/Mesh、异步任务平台、自动自进化、自动发布、多租户、RBAC、生产级 Trace、自研 Memory/Session/Runtime/模型路由、业务 UI、Marketplace 或 Hermes 核心补丁。

## 可删除策略

如果 Hermes 提供可靠的原生等价能力，应删除 Atelier 对应接缝，不为兼容继续保留重复抽象。即使工作台收缩，具体应用资产仍可继续作为原生 Hermes Profiles 存在。

## Kill / Pivot 条件

出现以下情况时停止扩张：

- Hermes 原生提供可靠的跨 Profile 调用、Trace、应用分组或 Review；
- `atelier_call` 不再需要；
- 第三个应用要求在 Atelier 核心加入业务特判；
- Builder 输出长期需要大规模人工重写；
- Reviewer 建议无法通过重复场景稳定验证；
- 开发者更愿意直接使用 Hermes Dashboard 和 Profiles；
- Atelier 维护成本超过其调试价值。

触发后依次优先：删除重复模块、收缩为一个 Hermes Plugin、收缩为 Builder Skill、把通用能力贡献给 Hermes 上游，并保留仍有价值的具体业务应用。
