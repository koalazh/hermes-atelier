# Hermes Atelier

## Status

**Archived product experiment**

Hermes Atelier 的产品化已经冻结。V2.1 是最后一个产品化原型；不规划 V3、V4。代码和文档仅用于研究、复盘与历史参考，不再作为推荐的 Hermes 应用工程入口。

## Why

核心用户路径可以由当前 coding agent 和一个领域 Skill 完成：对齐需求，在必要时冻结 PLAN 与 handoff，然后直接实现和验证。

Builder 到 coding agent 的交接增加了额外上下文转移；相对 V1 变轻，不等于相对一个 Skill 已经足够轻。工程质量能够证明实现认真，但不能证明项目有必要存在。因此，我们不再默认把“教 Agent 如何工作”建设成独立产品。

## Current experiment

当前实验位于 [koalazh/hermes-app-engineering](https://github.com/koalazh/hermes-app-engineering)。

它是一个独立、无 Runtime、可删除的 Experimental Skill，用真实 Hermes 应用任务检验 Skill-first 假设；它同样不宣称自己已经被证明是最终答案，也不是 Atelier 的继任版本。

## Historical material

- [V2.1 产品化阶段最终 README](docs/archive/V2.1_PRODUCT_README.md)
- [从产品化到 Skill-first 的转变记录](docs/SKILL_FIRST_TRANSITION.md)
- [历史架构说明](docs/ARCHITECTURE.md)
- [历史验证记录](docs/VALIDATION.md)
