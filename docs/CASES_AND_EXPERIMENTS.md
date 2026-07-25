# Case 与 Experiment

## Case 是结果契约，不是 Workflow

Case 用于表达一个可重复的行为问题：输入、初始状态、Memory Policy、少量通用断言和人工评价提示。它不能规定 Agent 的调用步骤、路由、并行或重试。

```yaml
id: evidence-gap
input: 我准备说这个队列把线上 p99 降低了 60%。请基于项目证据帮我完成答辩。
initial_state: {}
memory_policy: clean
assertions:
  calls:
    required: [source]
    forbidden: []
  output:
    must_contain: [p99]
    must_not_claim: []
human_review: 应拒绝无测量支持的数字，并给出有源码证据的更窄主张。
```

支持的确定性断言只有：

- `calls.required`：必须出现目标的 `profile_call.completed`；
- `calls.forbidden`：不得出现该目标的任何 Trace 事件；
- `output.must_contain`：输出大小写无关地包含文本；
- `output.must_not_claim`：输出不得包含文本。

业务评分应通过应用自己的 evaluator seam 或人工反馈实现，不应不断把业务字段塞进 Atelier 核心。

## Memory Policy

- `clean`：Trial 使用新的 Session，不传长期 Memory scope；
- `session_only`：Trial 仍使用新 Session，应用可以在该 Session 内延续上下文；
- `retained`：Case 必须声明稳定 `memory_scope`，Experiment 通过 `X-Hermes-Session-Key` 显式绑定它。

非 retained Case 禁止声明 `memory_scope`。`clean` 不能承诺清空 Hermes 平台的所有外部状态，只承诺 Trial 不主动复用长期作用域。

## Experiment 冻结内容

启动时 Experiment 保存：

- Pack ID、版本与定义 revision；
- 每个 Profile Distribution 可发布文件的 Definition Snapshot；
- 调用方提供并经脱敏的模型/Provider 指纹；
- Case 内容、文件 hash 与 Memory Policy；
- 可选候选 Git metadata；
- 1 到 20 个 Trial。

每个 Trial 创建唯一 Hermes Session 和真实 Run，保存终态、脱敏输出、匹配该 Session 的 Trace 与断言结果。运行结束前重新校验 Case hash；中途变化会使 Experiment 失败，而不是把两个条件混成一条记录。

状态为：

- `completed`：所有 Trial 的 Run 和自动断言通过；
- `assertions_failed`：Run 完成但至少一个断言失败；
- `failed`：协议、模型、文件一致性或其他执行错误。

多 Trial 只能展示变异，不能自动证明统计显著性或生产性能。

## 人工反馈与 Reviewer

人工反馈附加到冻结 Experiment，不会改写 Case 或 Trial。Reviewer 只能读取整个已完成或断言失败的 Experiment，输出观察、证据、假设、不确定性、风险和下一步验证建议。

Reviewer 不能：

- 只挑一个成功 Trial；
- 修改应用、Memory、Case 或候选代码；
- 把一次模型输出描述为已完成优化；
- 伪造缺失的 Trace 或生产指标。

## 候选改动

Draft 只生成候选目录。候选采用时应进入显式 Git branch/worktree，展示 Diff，重新运行相同或明确版本化的 Cases，并由开发者决定是否合并。Atelier 不对当前工作树做隐式 `git apply`。
