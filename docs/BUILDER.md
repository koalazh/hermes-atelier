# Builder、Reviewer 与批准边界

## Builder 的职责

`atelier-builder` 在生成任何应用之前，先调查用户目标、输入、预期输出、工具、数据、Memory 归属、安全边界与验收证据。默认优先使用单 Profile；只有工具或数据权限、长期知识、工作目录、资源、故障隔离、独立演进、复用价值或显著上下文质量差异成立时才拆分。

演示需要造成的拆分必须明确标记，并说明更简单的单 Agent 方案。Builder Skill 不固定角色模板、拓扑、模型、Prompt、Agent 数量、调用次数或业务流程。

## BUILD.md

每次 Build 只对应一个草稿目录和一份 `BUILD.md`。它包含：

- Original Request；
- Aligned Goal；
- Users and Inputs；
- Expected Output；
- Profile Boundaries；
- Tools and Data；
- Memory and Skill Ownership；
- HTTP Collaboration；
- Observability Needs；
- Acceptance Scenarios；
- Missing Real Integrations；
- Risks；
- Status。

这些标题作为 Builder 与后端之间的稳定契约保留英文，内容可以使用中文。`BUILD.md` 是目标和状态锚点，不是由 Atelier 执行的步骤图。

## Build 批准

Builder 可以在缺失信息会改变目标或安全边界时提出聚焦问题。它为每个 Profile 创建完整原生 Distribution，并在 `AWAITING_APPROVAL` 停止。自然语言中的“用户已经同意”不会改变后端状态。

批准时，后端会验证草稿中恰好有一个应用，拒绝 symlink 和密钥文件，校验不含 Workflow DSL 的 `app.yaml`，然后转入正式目录、安装 Profiles、创建端点、启动 Gateways，并登记内容派生的 definition revision。

若 Profile 安装或启动失败，后端会停止本次已经启动的 Gateways。清理成功后，正式目录移到忽略提交的诊断目录并删除失败注册；若清理本身失败，则保留应用和端点控制状态，避免产生 Atelier 无法管理的孤儿进程。

## Reviewer 与 Proposal

`atelier-reviewer` 只读冻结 Trace Bundle、用户反馈、场景、应用定义以及相关 SOUL/Skills。它不能读取真实密钥、无关 Memory 或整个用户目录，也不能修改应用、Memory、场景或自己的评价标准。

Reviewer 输出必须按以下顺序包含：

```text
OBSERVATIONS
EVIDENCE
HYPOTHESES
PROPOSED_CHANGES
RISKS
VALIDATION_PLAN
CONFIDENCE
```

完成 Review 后，Builder 在另一个隔离草稿中只生成 `candidate.patch`。后端拒绝空 Patch、损坏 Patch、跨应用路径、密钥、运行态、Atelier 核心、Builder 或 Reviewer 路径。即使 Patch 路径合法，若它编码固定业务流程或超出证据，用户仍应拒绝。

Patch 应用需要显式批准和 dry-run。若后续 Profile 更新失败，后端会反向应用 Patch、恢复应用注册并重装原始受影响 Profiles；任何回滚不完整都会明确记录为 `patch_apply_failed`，而不会宣称成功。
