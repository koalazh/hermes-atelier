# 从 V1 迁移到 V2

## 核心变化

V1 把 Atelier Run、SQLite、Endpoint/PID Registry、后台 Profile 任务和 `atelier_call` 放进应用运行路径。V2 删除这层所有权：应用直接运行在 Hermes 上，Studio 只保留可删除的开发证据。

| V1 | V2 |
| --- | --- |
| Atelier `atelier_call` | 独立 App Plugin `profile_call` |
| Atelier Root Run / Span | Hermes 原生 Session / Run，加可选 Trace 索引 |
| `.atelier/atelier.db` 运行事实源 | Hermes 运行态；`.atelier/v2` 只存开发证据 |
| Endpoint/PID Registry 与后台 supervisor | Hermes `gateway start/stop/status` |
| 一次性 Build | Builder 原生多轮 Session + 显式 Drafter |
| Playground 包装 Chat | 直接 Hermes Chat/Session/OpenAI API |
| 单 Run Review/Proposal/Replay | 冻结 Case/Experiment/Trial + Git 候选 |
| `app.yaml` 物理 Profile/场景 | V2 逻辑 Agents/App Pack/Cases/Contracts |

## Manifest 迁移

不要机械改字段。先明确唯一公开入口、内部逻辑 Agent、每个 Distribution、权限边界、公开 OpenAI 端点和状态策略，再写 `schema_version: 2`。

V2 禁止把 V1 Scenario 中的隐式调用顺序搬进 `app.yaml` 或 Case。路由行为应在入口 SOUL/Skill 中表达，Case 只验证结果和真实调用事实。

旧 `scenarios/` 可在迁移期保留作历史对照，但活动 CLI、Manifest 和 Release 只引用 `cases/`。

## Runtime 迁移

1. 从每个业务 Distribution 移除 Atelier Plugin 依赖；
2. 对确有跨 Profile HTTP 需求的调用方使用 Pack 的 `collaboration: [profile_call]`；
3. 由 `atelier release` 将 Plugin 注入允许发起调用的 Distribution；
4. 在 fresh `HERMES_HOME` 中 install/configure/start，不复用 V1 Registry、PID、端口或 `.atelier`；
5. Consumer 为实例选择新物理 Profile 名和端口，验证外部 Session 与内部 Run；
6. 确认 Atelier 停止时应用仍工作，再下线 V1 Studio 运行态。

不要把 V1 `task_id == session_id`、Root/child Session 命名或 Atelier Endpoint 数据迁移到 `local/app-runtime.json`。V2 映射只包含逻辑身份、物理 Profile、loopback URL、API Key 环境变量名和 allowlist。

## Builder 与候选迁移

V1 Builder 写入当前应用草稿并可进入 Proposal/Patch。V2 Builder 规划 Profile 无写权限；只有开发者显式触发 Drafter，且输出必须通过 V2 AppPack Validator。Draft 仍只是候选。

已有 Proposal 不应自动重放。把需要保留的改动整理为 Git branch/worktree，展示 Diff，以冻结 Experiment 重新验证后人工合并。

## 状态与回滚

V2 不迁移 Atelier SQLite 中的 Run/Span/PID 为 Hermes 状态。若历史数据需要审计，应只读导出并明确标记为 V1 历史证据。

应用 Memory/Session 的迁移由 Consumer 和 Hermes 拥有。首次 V2 安装建议使用新的实例名；需要复用长期 Memory 时，先确认 `state_compatibility` 和业务范围，再显式选择 stable scope。

回滚 V2 Pack 使用旧 release 的 `./app update` 或 Hermes 原生 Profile Distribution install。保留旧 release 目录和 `app.lock`，不要依赖 Atelier 工作树。

## 兼容代码状态

仓库中的 V1 services、SQLite Store、旧 Dashboard bundle 和旧脚本暂时作为迁移期回归证据保留，以证明 V2 没有破坏已测试的历史行为。它们不被 V2 `plugin.yaml`、CLI entry point 或 `index_v2.js` 引用，也不得用于新安装。

当下游迁移完成且相关回归价值消失时，应在独立删除任务中连同 V1 tests 一起移除，避免边迁移边重写历史证据。

## 迁移完成检查

- 发布目录中没有 Atelier Plugin、SQLite、`.env`、Memory、Session、Trace、PID 或 `local/`；
- Studio/Dashboard 停止后，入口 Chat 和内部 `profile_call` 仍成功；
- 真实返回包含目标 Profile、Session、Run 与 call ID；
- V2 Case 不含 Workflow key，Experiment 冻结定义与模型条件；
- 更新 smoke 失败能恢复旧映射或明确报告回滚失败；
- 只有 Consumer 选择的入口端口对外暴露。
