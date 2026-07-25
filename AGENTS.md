# Hermes Atelier V2.1 Coding Agent 工作指南

## 长期不变量

- Hermes 拥有 Profile、Gateway、Session、Run、Memory、模型、工具和进程生命周期；不修改 Hermes 核心源码。
- Atelier 是可删除的开发工坊。已发布 App Pack 在 Dashboard、`.atelier`、Builder、Drafter 和 Reviewer 都不存在时仍应通过普通 Hermes Session 与 OpenAI-compatible HTTP 工作。
- Agent 决定业务行为。Atelier 不因 Trace、UI 或 Case 的可观察性而关闭 Hermes 原生协作，也不编码业务 Workflow。
- `profile_call` 是可选、独立于 Atelier 的应用 Plugin；它不得依赖 `.atelier`。
- Secret 不进入 App Pack、`app.lock`、Trace、文档或 Git。真实密钥只能进入 Consumer 拥有、权限为 `0600` 的 Profile `.env` 或进程环境。
- 修改与证据必须诚实可追溯：声明、配置记录、live 事实和推断要分开，失败不能伪装成成功。

## 修改原则

1. 先检查 `git status --short`，保留用户改动；Bugfix 先建立可复现调用链。
2. 读取直接相关代码、测试与文档，以当前 Hermes 能力为准，不凭旧设计记忆推断。
3. 做能满足需求的最小改动，不增加新的 Runtime、状态机、协议或推测性扩展点。
4. 每条改动都要有风险相称的验证；与本次目标无关的问题只报告，不顺便修复。

## 组件边界

| 路径 | 职责 |
| --- | --- |
| `plugin/atelier/` | Core 的 Design/Handoff/App Pack Lens/Delivery，以及可选 Assurance Lab。 |
| `plugin/profile_call/` | 独立的逻辑 Profile 调用原语。 |
| `profiles/atelier-builder/` | 多轮意图对齐并产出 `PLAN.md` 与 `IMPLEMENTATION_HANDOFF.md`。 |
| `profiles/atelier-drafter/` | 可选 Hermes Draft；`terminal.cwd` 不是安全沙箱，产物必须再次验证。 |
| `profiles/atelier-reviewer/` | 可选、只读的证据 Reviewer；不是 Core 启动依赖。 |
| `apps/<app-id>/` | Schema V2 App Pack、Profile Distributions、业务能力、Cases 与 Consumer 文档。 |
| Consumer `HERMES_HOME` | Hermes Profile、凭据、Memory、Sessions、日志、PID 与运行映射。 |

App Pack Schema V2 当前冻结。保留明确 schema 与 Pydantic `extra="forbid"`；不要用递归自然语言关键词检查来执法设计哲学。`allowed_calls` 是 `profile_call` Tool Policy 与凭据最小化声明，不是跨进程强授权，也不是路由图。

Case 描述输入、状态、Memory Policy、通用结果断言和人工评审提示。只有真实权限、数据来源或公共合同要求特定 Profile 时才使用 `calls.required`，普通质量 Case 不规定 Agent 的解题路线。

## 安全与失败语义

- Gateway 默认绑定 `127.0.0.1`。逻辑映射只含 self 与允许目标，保存 Key 环境变量名而非 Secret；同一 OS 用户下的 Profile 仍不构成强进程隔离。
- Pack、Draft、Case、Distribution 与候选路径必须留在声明根内，拒绝绝对路径、`..`、symlink 越界和运行态。
- Trace 使用独立短超时；Trace 失败只能降级可见性，不能阻塞业务结果。缺少 Trace 不等于没有协作。
- 子 Run 异常后 best-effort stop，严格区分 `stop_requested`、`stop_confirmed` 与 `stop_unknown`。
- update/rollback 是 local、best-effort、experimental，不宣称事务原子性，也不扩展成部署平台。

## 验证与交付

| 改动 | 最低门禁 |
| --- | --- |
| Python | 相关 `uv run pytest -q tests/<file>.py`，再 `uv run ruff check .` |
| Pack/运行边界 | 确定性失败路径；高风险变化使用 fresh `HERMES_HOME` 做真实 Hermes smoke |
| Dashboard | API 测试、`node --check plugin/atelier/dashboard/dist/index_v2.js` 与真实浏览器检查 |
| 发布/依赖 | `uv sync --extra dev`、`uv run pytest -q`、`uv run ruff check .`、`uv build` |
| 文档 | `uv run pytest -q tests/test_documentation.py` |

面向人的 README、`AGENTS.md` 和 `docs/**/*.md` 使用中文说明。真实 smoke 只证明链路可执行，不证明生产质量。禁止提交 Secret、Memory、Sessions、Trace 或运行态；未经明确要求不 push、部署或创建 PR。
