# V2 验证证据与已知限制

验证日期为 2026-07-25，目标环境是本地已安装的 Hermes Agent 0.19.0。Hermes 核心只读使用，没有修改或提交上游代码。

## 当前 Hermes 能力审计

源码与真实探针确认 Hermes 提供 Profile Distribution install/update、Profile config、原生 Gateway 生命周期、`/api/sessions` 多轮 Chat、OpenAI 兼容 Chat/Responses、异步 `/v1/runs` 与 SSE、Plugin context 和 Memory scope。

同时确认当前 multiplex Gateway 的 Plugin Manager 为进程级单例，只从默认 Hermes Home 发现一次 Plugins，不能安全承载示例的 Profile 私有业务 Plugins。因此 V2 release 为每个物理 Profile 使用一个显式 loopback Gateway；该取舍应在 Hermes 提供 Profile-scoped Plugin registry 后重新评估。

## 确定性验证

V2 自动化覆盖：

- Manifest 逻辑身份、唯一入口、权限、路径、Workflow key 和运行态过滤；
- Definition Snapshot、release、`app.lock`、smoke Case 和 `profile_call` 注入；
- wrapper install/configure/start/stop/status/update，以及新 smoke 失败后的旧映射回滚；
- 独立 `profile_call` 的 allowlist、真实目标元数据、Memory scope、目标错误与 Trace 降级；
- Builder 同一 Hermes Session 多轮对话、状态转换、独立 Drafter 和 V2 Draft 验证；
- Case/Memory Policy、Experiment 冻结、Trial/Trace/断言、反馈与整个 Experiment Review；
- V2 API、CLI、Dashboard bundle 和 Studio 文件证据存储。

全量 pytest、Ruff、Dashboard JavaScript 语法和 Python sdist/wheel 构建是最终交付门禁；精确结果见“最终门禁”，不把测试数量解释为生产质量指标。

## Mini VOC fresh runtime

在全新、与开发 Studio 分离的 `HERMES_HOME` 中发布并安装 Mini VOC，启动三个原生 Profile Gateways。入口使用普通外部 Session `external-consumer-session-002`，真实产生两次 `profile_call`：

- Product 目标物理 Profile 为 `mini-voc-test--product`，目标 Session `pc_34b…`，Hermes Run `run_a0d704…`，并执行 `voc_product_lookup`；
- Transaction 目标物理 Profile 为 `mini-voc-test--transaction`，目标 Session `pc_c9ff…`，Hermes Run `run_d506…`，并执行 `voc_transaction_lookup`。

最终回答引用模拟记录 `PRD-LOGIN-17` 与 `ORD-1001`，且明确说明不是生产数据。验证期间 Atelier Dashboard 未运行，fresh runtime 不含 `.atelier`，证明应用主路径不依赖 Studio。随后停止并清理了本任务启动的 Gateways、Profile 运行态和 launchd 条目。

首次真实调用使用了错误模型名并诚实返回 Provider 400；改为用户指定的有效模型标识后成功。这证明失败没有被 wrapper 或 Plugin伪装为业务结果。

## Builder 与 Drafter 真实会话

真实 Hermes Builder Session `atelier_design_7410564f…` 完成两轮对话：第一轮为 `NEEDS_INPUT`，开发者补充后进入 `PLAN_READY`。显式 Drafter Run `run_dfecdb…` 生成并通过验证的 V2 Pack，包含 `app.yaml`、Case 和 Profile Distribution。

验证还发现并修正了三个真实边界误解：`/v1/runs` 的 `session_id` 不会载入 Chat 历史；规划 Profile 不应拥有写工具或 Session 搜索；Drafter 必须收到精确 V2 schema 并由后端严格验证。最终实现改用 `/api/sessions/{id}/chat`、分离 Builder/Drafter 权限并保留严格 Validator。

相关 Builder/Drafter Gateways 在验证后已停止并清理。

## Project Defense fresh runtime

全新安装首次暴露出端口分配缺陷：Definition Snapshot 按 Agent ID 排序，导致 `--gateway-port 19500` 实际指向 Architecture，而公开 Host 在 19502。修复后入口始终占 base port，并增加“entry 不是字母序首位”的回归。

修复后的普通外部 Session `external-defense-host-session-001` 连续完成三轮答辩，真实调用：

- Source：目标 `defense-v2-test--source`，Session `pc_4d6b…`，Run `run_2c3ab3…`；
- Architecture：目标 `defense-v2-test--architecture`，Session `pc_728b…`，Run `run_e902b1…`；
- Coach：目标 `defense-v2-test--coach`，Session `pc_9b57…`，Run `run_ecc45c…`。

三次调用都返回真实 `call_id` 且 `trace_degraded=false`。第一轮依据 Source 的 `README.md` 和 `queue.py` 拒绝无来源的“p99 降低 60%”；第二轮沿用同一 Hermes Session，把源码事实、架构推断和未知分层；第三轮按需调用 Coach。Atelier Dashboard 未运行。

真实链路还发现两项不能由单测替代的行为：多专家 Session Chat 超过通用 30 秒读取超时，因此 Chat 改为长请求且不自动重试；仅传 `X-Hermes-Session-Key` 不会自动写入 Memory。Hermes 0.19.0 的 `MEMORY.md` / `USER.md` 是物理 Profile 全局文件，不能承担 caller isolation。

Project Defense 因此把长期偏好收敛为应用自己的 Coach Plugin：原始 scope `defense-v2-scoped-final` 只在调用边界出现，`profile_call` 使用 SHA-256 派生 `140f068bfb5d657696921f3c`，目标 Session 只包含该派生 ID。真实写入 Run `run_a932…` 后，另一个入口 Session 通过 Run `run_cfcb1…` 读回同一偏好；不带 scope 的 clean Run `run_f6cb…` 明确返回无 caller scope。随后一次真实 `app update` smoke 成功，Coach `local/project-defense-coach-memory/` 状态仍存在。四个业务 Profile 均禁用 Hermes 全局 Memory/User Profile，Coach 只有在 `defense_coach_memory` 返回 `stored` 后才能声称保存。

真实 Experiment `5fe7aa…` 冻结 Pack、模型、clean Memory Policy、Case 和 Trial，入口 Run 为 `run_1d661…`，Source 目标 Run 为 `run_ab464…`。独立 Reviewer Profile 使用 Run `run_887f…` 审核整个 Experiment，指出模型虽然拒绝 p99 数字，却又虚构 Redis 与服务数量。根据该证据，Case 增加两个 `must_not_claim`。Delta Experiment `37dbe7…` 随后揭示 Host 绕过 `profile_call` 使用通用 delegation，导致没有可归因 Trace；修复为所有业务 Profile 禁用 delegation。最终 Experiment `a82c6b…` 的入口 Run `run_b069…` 真实调用两个 Source Runs `run_a70b…`、`run_a49e…`，四项断言全部通过。

这轮真实输出仍把 Pack 内样例目录误称为宿主 `/Users/koala`。Source 合同随后收紧为只描述 Pack-owned sample workspace。模型偶尔仍会生成假设性数字；Prompt、Case 和 Reviewer 可以暴露或降低这类风险，但不能把随机模型输出提升为确定性事实能力。

## Dashboard 浏览器验收

Hermes 0.19.0 Dashboard 在 loopback `19610` 上进行真实浏览器验收。首次加载发现 V2 静态入口可见，但 API 日志为 `No module named 'plugin'`：独立用户插件仍依赖仓库命名空间。修复为包内相对导入并增加 standalone plugin 回归后，Hermes 成功挂载 `/api/plugins/atelier/`。

最终浏览器检查覆盖 Design、Run & Observe、Evaluate、Release 四页；两个 Pack、7 个 Case、revision、唯一 public entry 均可见。Run & Observe 以真实 Trial Session 加载四条 `profile_call` started/completed 事件和两个目标 Run ID；浏览器 console 无 warning/error。验收后只停止本任务的 Dashboard，保留用户原有 Dashboard。

## 最终门禁

最终结果：92 个 pytest 全部通过；Ruff、`node --check plugin/atelier/dashboard/dist/index_v2.js`、`uv build` 与 `git diff --check` 通过。Mini VOC（4 Cases）和 Project Defense（3 Cases）均在 fresh 临时目录完成 validate/release，release 中没有 `.env`、Atelier 数据、`__pycache__` 或 Python bytecode，wrapper 可执行。仓库 Secret 形状与私钥文件扫描无命中；本任务使用的 19500–19504、19600、19610 均无监听，对应 launchd 条目已移至废纸篓。用户原有 Dashboard 未停止。

## 已知限制

- 真实模型输出具有随机性，smoke 只证明协议和资产链路可执行；
- Prompt/Case 不能证明模型永不虚构，肯定性业务主张仍需来源证据或人工审阅；
- Trace Sink 是可选开发观测，不是生产审计；缺少 Trace 不能独立证明没有调用；
- update 是多条 Hermes/文件/网络操作的 best-effort 回滚，不是事务部署；
- 当前每 Profile 一个 Gateway 是 Hermes Plugin 隔离限制下的取舍；
- V1 compatibility 模块仍在仓库中作为回归证据，但不在 V2 活动 manifest、CLI 或 Dashboard 路径；
- Atelier 不提供多租户、企业 RBAC、远程 Registry、生产 Agent Mesh、蓝绿发布或自动优化。
