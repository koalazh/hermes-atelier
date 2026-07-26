# Builder、Drafter 与 Reviewer 边界

## 多轮设计

Atelier Builder 是完整 Hermes Profile，但规划阶段是只读的。Studio 为每个 Design 创建稳定 Hermes Session，调用 `/api/sessions/{id}/chat`，并在后续轮次复用同一 Session。开发者可以回答问题、纠正目标、要求更简单的边界或补充验收条件。

Builder 输出必须以以下状态之一结束：

```text
DESIGN_STATUS: NEEDS_INPUT
DESIGN_STATUS: PLAN_READY
```

缺失信息会改变目标、安全、数据或验收时使用 `NEEDS_INPUT`；其余技术取舍由 Builder 完成。`PLAN_READY` 后 Studio 写出 `PLAN.md` 和 `IMPLEMENTATION_HANDOFF.md`，但不会修改应用源码。

## 拆分原则

默认优先单 Profile。只有工具/数据权限、长期知识、工作目录、资源、故障隔离、独立演进、复用或显著上下文差异成立时才拆分。为了演示造成的拆分必须明确标记，并给出更简单方案。

PLAN 是决策锚点。handoff 面向开发者选择的 Coding Agent，至少覆盖原始需求、对齐目标、多 Profile 必要性、Profile 边界与理由、工具/数据/权限、Session/Memory/Skill 归属、推荐协作原语、App Pack 与 HTTP 边界、Cases、未接入系统和非目标；它不是固定步骤 Workflow。

handoff 中的 App Pack 示例必须遵守冻结的 V2 Schema：`app.yaml` 只声明逻辑
Profile、entry、HTTP、状态和协作声明；Hermes Distribution 使用
`distribution.yaml`、`config.yaml`、`SOUL.md`，不存在 Atelier 自定义的
`profile.yaml`。模型、Provider、端口和 Gateway Secret 由 Consumer 通过 Hermes
原生命令配置，不进入 Pack，也不由 Builder 选择。

## 权限切换

规划 Profile 的 config 默认禁用 terminal、file、code_execution、session_search、memory 和 delegation。它不能借规划请求写仓库、搜索其他 Session 或委派有副作用的 Agent。

默认动作是 `Export handoff`，可以交给 Codex、Claude Code、Hermes、其他 Coding Agent 或人工实现。只有开发者选择 `Generate with Hermes`，Studio 才把 PLAN、handoff 与 Draft 目录发送给独立 `atelier-drafter`。`terminal.cwd` 不是安全沙箱；Drafter 不应获得无关 Secret，后端仍验证恰好一个 V2 App Pack。

Draft 不等于采纳、安装、启动、提交或批准。失败 Draft 不得进入正式应用。

## 候选与 Git

需要继续演进的 Draft 或人工改动应进入明确 Git branch/worktree。Atelier 记录候选 branch、worktree 和 diff metadata，但不对当前工作树执行隐式 Patch。

候选必须展示 Diff，以冻结 Case/Experiment 验证，并由开发者决定是否合并。Git 是定义历史事实源；Atelier 不建立 Proposal 数据库代替 Git。

## Reviewer

Assurance Lab 默认导出冻结 evidence bundle；`Review with Hermes` 是可选后续。`atelier-reviewer` 只读取一个完整、冻结且已经结束的 Experiment。它输出观察、证据、假设、不确定性、风险和验证建议，不修改 App、Case、Memory、模型或评价标准。

Reviewer 不能把一次成功输出称为“优化完成”，不能只选择有利 Trial，不能依据缺失 Trace 推断没有调用，也不能把模拟数据描述为生产事实。任何改进建议都必须回到 Git 候选和新 Experiment。

Builder、Drafter、Reviewer Distribution 不携带模型默认值，也不要求 Atelier
专用模型变量。安装后使用 Hermes 原生 `config set` 或 Dashboard Models 为每个
Profile 独立选择模型；Atelier 只读取真实运行配置用于证据，不管理模型。对于自定义
OpenAI-compatible Provider，优先让 Hermes 配置引用 Profile `.env` 中的专用
`key_env`，避免复用全局 `OPENAI_API_KEY` 造成凭据歧义。

## 失败语义

- Hermes Session 创建或 chat 失败：Design 保留此前对话证据并报告失败；
- Builder 未给出可识别状态：不允许进入 Draft；
- Drafter Run 失败或产物不合法：状态为 Draft 失败，不触碰正式应用；
- Reviewer Run 失败：Experiment 本体保持不变，可在修复外部条件后重试 Review；
- Studio 存储失败：不得将未持久化结果伪装为已保存设计或评价。
