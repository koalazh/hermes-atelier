# ADR 008：规划与写入使用独立权限 Profile

状态：已接受

Builder 通过 Hermes 原生 Session 多轮对齐，规划 Profile 默认禁用文件、终端、代码执行、历史 Session 搜索、Memory 和委派。`PLAN_READY` 不产生文件。

只有开发者显式触发 `Generate Draft` 才调用独立 Drafter Profile。Drafter 只写指定 Draft 根，产物必须通过严格 V2 AppPack Validator。Draft 不等于采用、安装、提交或批准。

候选演进使用 Git branch/worktree、可见 Diff 和冻结 Experiment，不再由 Atelier 对当前工作树应用 Patch。Reviewer 只分析完整 Experiment，不能修改候选或宣称一次输出已经完成优化。
