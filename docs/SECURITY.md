# V2 安全边界

## 信任模型

Atelier V2 面向可信本地开发仓库，不是操作系统沙箱、多租户控制面或生产安全边界。Hermes Gateway 与 Dashboard 默认只绑定 `127.0.0.1`。需要更强文件、进程和网络隔离时，应使用 Hermes 支持的隔离后端和 Consumer 基础设施。

## Secret 所有权

真实模型 Key 和 Gateway API Key 只存在于 Consumer 进程环境以及 Hermes Profile `.env`。薄 wrapper 写 `.env` 后设置 `0600`，但不把 Secret 写入：

- `app.yaml`、Distribution、Case、Contract 或 `.env.example`；
- `app.lock`、`local/app-runtime.json` 或 Atelier Store；
- Trace、错误、模型指纹、Dashboard 响应、文档或 Git。

命令行传递的是环境变量名，不是 Secret 值。`.env.example` 只能包含空值或明显占位符。

## 网络与身份

每个物理 Profile 使用独立 loopback Gateway，并为每个目标生成独立 API Key。Pack 只有一个 `public` entry；内部 Profile 仍需认证，但不应加入外部 ingress。

`profile_call` 从当前 Profile 的最小运行映射确定来源，按 `allowed_calls` Tool Policy 校验目标，并从目标声明的环境变量读取 Key。调用方只获得 self 与允许目标的映射和 Key。映射缺失、越权或 Secret 缺失时失败关闭。

这不是强 RBAC：Hermes Profiles 仍运行在同一 OS 用户下，`terminal.cwd` 也不是文件系统沙箱。拥有通用终端或自定义 HTTP 的 Agent 可能读取同用户可访问的其他文件。需要强隔离时由 Consumer 使用独立用户、容器、网络或未来 Hermes 原生权限能力。

当前不使用 multiplex，因为 Hermes 0.19.0 的 Plugin Manager 无法隔离 Profile 私有 Plugins。这是能力约束，不是允许任意暴露多个端口的理由。

业务 Profiles 不再仅因 Trace 或 UI 观测而禁用 delegation。是否禁用工具必须来自真实数据、权限、工作目录或安全边界。`apps/delegation-note` 明确验证原生协作可在没有 `profile_call` Trace 时工作。

## 路径与发布边界

App Pack Distribution、Case、Contract、公开输出 Contract 与 wrapper `instance` 必须是受约束的相对标识或路径。Validator、Release 和 wrapper 拒绝根目录逃逸；wrapper 还拒绝 `app-packs` 状态根或具体实例目录的 symlink。Release 过滤 `.env`、Memory、Sessions、Logs、Trace、PID、`local/`、`__pycache__`、Python bytecode 与 Atelier 数据，并在临时 staging 内扫描常见 `*_API_KEY`、`*_SECRET`、`*_TOKEN`、`*_PASSWORD`、`*_KEY` credential 赋值形状，失败时不会暴露半成品目标目录。

Builder 规划阶段无写权限。Drafter 的目标 cwd 不是安全沙箱，必须使用独立 Profile、最小 Secret、显式用户动作和 Validator 限制风险。候选变更进入 Git branch/worktree，不对当前工作树执行隐式 Patch。

## 状态与删除

Hermes 拥有 Profile、Memory、Sessions、Run、PID 和日志。Atelier `.atelier/v2` 只保存开发证据，可以删除。Pack update 保留 Consumer `.env`、Memory、Sessions 与 `local/`，即使 Manifest 标记 `reset_recommended` 也不静默删除。

V2 不提供隐式 uninstall。删除 Profile 和长期状态必须由 Consumer 明确指定物理目标。

## 失败与回滚

- Trace Sink 使用独立短 timeout；失败不阻断 dispatch 或已成功的业务结果，但必须标记 `trace_degraded`；
- 子 Run 在 timeout、cancel、SSE/网络/解析异常后 best-effort stop，停止请求与确认终态不得混写；
- 模型/目标 Gateway/鉴权失败不能返回伪造结果；
- update smoke 失败触发 best-effort 恢复旧 Distribution、映射、配置与服务；
- 回滚不是跨进程事务，任何恢复失败必须显式上抛；
- `gateway stop` 的意义由 Hermes 原生命令决定，wrapper 不维护自己的 PID 或伪造健康状态。

## 发布前检查

运行仓库测试、Ruff、build、Pack validate/release 和 fresh runtime smoke；用只输出文件名的扫描检查 Key 形状；确认 release 中没有运行态资产；停止本任务启动的全部 Gateway。真实模型输出应按不可信外部输入处理，不能把其自然语言当作权限或运行证据。
