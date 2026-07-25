# Case 与 Experiment

## Case 是结果契约，不是 Workflow

Case 用于表达一个可重复的行为问题：输入、evaluation context、Memory Policy、少量通用断言和人工评价提示。它不能规定 Agent 的调用步骤、路由、并行或重试。

```yaml
id: evidence-gap
input: 我准备说这个队列把线上 p99 降低了 60%。请基于项目证据帮我完成答辩。
evaluation_context: {}
memory_policy: new_session
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

`calls.required` 只应在真实权限、可信数据来源或公共合同要求特定 Profile 时使用。普通质量 Case 优先检查可信证据、越权、虚构、未知表达、业务合同和专家失败降级，不把可观察调用树当作通用正确性。

`evaluation_context` 只是作为 JSON 追加到 Trial instructions，没有执行 setup hook、fixture 或状态写入，因此不叫 `initial_state`。旧字段仍可兼容读取。

## Memory Policy

- `new_session`：只保证新的 Hermes Session，不保证 Profile Memory、`local/` 或外部系统为空；
- `retained_scope`：Case 必须声明稳定 `memory_scope`，入口与明确支持 scope 的状态工具使用该 caller scope；
- `fresh_instance`：要求安装记录证明使用新物理 Profiles/HERMES_HOME，才可声明没有旧 Session、Memory 与 local state。

旧 `clean | session_only | retained` 分别兼容迁移为 `new_session | new_session | retained_scope`；新输出和文档不再把新 Session 称作严格 clean。非 `retained_scope` 禁止声明 `memory_scope`。

## Experiment 冻结内容

Experiment 不接受调用方自报的 endpoint 或模型指纹。启动前使用 `configured_runtime_attestation` 校验 release hash、安装资产、运行映射、逐 Profile config hash 与配置记录。`live_runtime_probe` 是独立、轻量的当前状态证据，不用猜测补全 configured 记录。

启动时 Experiment 保存：

- Pack ID、版本与定义 revision；
- 每个 Profile Distribution 可发布文件的 Definition Snapshot；
- configured attestation 得到的逐 Profile 配置记录与 release Definition Snapshot；
- Case 内容、文件 hash 与 Memory Policy；
- 可选候选 Git metadata；
- 1 到 20 个 Trial。

每个 Trial 创建唯一 Hermes Session 和真实 Run，保存终态、脱敏输出、匹配该 Session 的 Trace 与断言结果。运行结束前重新执行 runtime attestation 并校验 Case hash；定义、模型或 Case 中途变化会使 Experiment 失败，而不是把两个条件混成一条记录。

状态为：

- `completed`：所有 Trial 的 Run 和自动断言通过；
- `assertions_failed`：Run 完成但至少一个断言失败；
- `failed`：协议、模型、文件一致性或其他执行错误。

多 Trial 只能展示变异，不能自动证明统计显著性或生产性能。

## 人工反馈与 Reviewer

人工反馈附加到冻结 Experiment，不会改写 Case 或 Trial。默认可导出 JSON evidence bundle；只有开发者选择 `Review with Hermes` 时才需要 Reviewer Gateway。Reviewer 读取整个已完成或断言失败的 Experiment，输出观察、证据、假设、不确定性、风险和下一步验证建议。

Reviewer 不能：

- 只挑一个成功 Trial；
- 修改应用、Memory、Case 或候选代码；
- 把一次模型输出描述为已完成优化；
- 伪造缺失的 Trace 或生产指标。

## 候选改动

Draft 只生成候选目录。候选采用时应进入显式 Git branch/worktree，展示 Diff，重新运行相同或明确版本化的 Cases，并由开发者决定是否合并。Atelier 不对当前工作树做隐式 `git apply`。

候选 Experiment 必须声明 `branch`、Git worktree 根目录、`commit`、`baseline_commit`、`baseline_source_revision` 和 `baseline_case_hash`。Atelier 不信任这些自报值：运行前会要求 worktree 干净，核对实际 branch/HEAD、baseline 的规范 commit 与祖先关系、runtime attestation 的 Git provenance，并从 Git tree 重新计算 baseline 与 candidate Pack revision、读取 baseline Case、计算限定到所选 Pack 的实际 Diff。candidate 必须真正改变该 Pack；只提交仓库其他文件、修改 Case、伪造 revision、使用不存在的 worktree 或与已安装 runtime 不同的 commit 都会被拒绝。Case 变化必须作为新的评价条件单独运行，不能和 Profile 变化合并成“改进”。
