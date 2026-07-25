# Builder、Drafter 与 Reviewer 边界

## 多轮设计

Atelier Builder 是完整 Hermes Profile，但规划阶段是只读的。Studio 为每个 Design 创建稳定 Hermes Session，调用 `/api/sessions/{id}/chat`，并在后续轮次复用同一 Session。开发者可以回答问题、纠正目标、要求更简单的边界或补充验收条件。

Builder 输出必须以以下状态之一结束：

```text
DESIGN_STATUS: NEEDS_INPUT
DESIGN_STATUS: PLAN_READY
```

缺失信息会改变目标、安全、数据或验收时使用 `NEEDS_INPUT`；其余技术取舍由 Builder 完成。`PLAN_READY` 只是可执行设计，不会写文件。

## 拆分原则

默认优先单 Profile。只有工具/数据权限、长期知识、工作目录、资源、故障隔离、独立演进、复用或显著上下文差异成立时才拆分。为了演示造成的拆分必须明确标记，并给出更简单方案。

PLAN 至少覆盖目标、用户与输入、输出、逻辑 Agent 边界、工具与数据、Memory、协作、安全、Cases、Contracts、缺失真实集成、风险和验收证据。它不能把业务步骤编码进 Atelier 核心。

## 权限切换

规划 Profile 的 config 默认禁用 terminal、file、code_execution、session_search、memory 和 delegation。它不能借规划请求写仓库、搜索其他 Session 或委派有副作用的 Agent。

只有开发者显式触发 `Generate Draft`，Studio 才把已批准 PLAN 发送给独立 `atelier-drafter` Profile。Drafter 只被允许写一个指定 Draft 目录，且必须生成恰好一个 V2 App Pack。后端随后执行相同的 AppPack Validator；非法路径、Workflow key、缺失 Distribution 或多个 Pack 都会失败。

Draft 不等于采纳、安装、启动、提交或批准。失败 Draft 不得进入正式应用。

## 候选与 Git

需要继续演进的 Draft 或人工改动应进入明确 Git branch/worktree。Atelier 记录候选 branch、worktree 和 diff metadata，但不对当前工作树执行隐式 Patch。

候选必须展示 Diff，以冻结 Case/Experiment 验证，并由开发者决定是否合并。Git 是定义历史事实源；Atelier 不建立 Proposal 数据库代替 Git。

## Reviewer

`atelier-reviewer` 只读取一个完整、冻结且已经结束的 Experiment。它输出观察、证据、假设、不确定性、风险和验证建议，不修改 App、Case、Memory、模型或评价标准。

Reviewer 不能把一次成功输出称为“优化完成”，不能只选择有利 Trial，不能依据缺失 Trace 推断没有调用，也不能把模拟数据描述为生产事实。任何改进建议都必须回到 Git 候选和新 Experiment。

## 失败语义

- Hermes Session 创建或 chat 失败：Design 保留此前对话证据并报告失败；
- Builder 未给出可识别状态：不允许进入 Draft；
- Drafter Run 失败或产物不合法：状态为 Draft 失败，不触碰正式应用；
- Reviewer Run 失败：Experiment 本体保持不变，可在修复外部条件后重试 Review；
- Studio 存储失败：不得将未持久化结果伪装为已保存设计或评价。
