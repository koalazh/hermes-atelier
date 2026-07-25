# ADR 005：改进必须经人工批准

状态：已被 ADR 008 取代

V1 使用候选 Patch 和后端 apply。V2 保留 Reviewer 只读与证据约束，但候选修改改由显式 Git branch/worktree、Diff 和 Experiment 管理。

任何组件都不能根据一次未经验证的输出宣称已经完成自我改进。
