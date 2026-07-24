# 安全边界

## 信任模型

Atelier V1 是面向可信本地仓库的开发 Plugin。Dashboard 与所有 Profile API Server 默认只绑定 `127.0.0.1`；启动脚本拒绝 `0.0.0.0`，文档也不提供公网部署方式。启用不可信 Plugin 时，不得把 Hermes Dashboard 暴露到公共网络。

项目本地 `HERMES_HOME` 把 Hermes 状态与 `~/.hermes` 隔离，但它不是操作系统安全沙箱。需要更强文件、进程或网络隔离时，应使用 Hermes 支持的 Docker 等执行后端。

## 密钥与浏览器边界

API Key 只存在于 Git 忽略、权限为 `0600` 的 Profile `.env`。SQLite 只保存 host、port、status 和 PID，不保存 Profile API Key。浏览器响应只返回端点和缺失变量名，不返回值，也不会直接调用业务 Profile。

Authorization Header、符合密钥形状的字符串和常见 secret assignment 会从事件、摘要、反馈包、错误和 Builder 输入持久化中脱敏。真实密钥不得进入 `.env.example`、`app.yaml`、Distribution、Trace Bundle 或 Git 历史。

## 路径与修改边界

所有 Profile 名称、Profile source、scenario、draft、Trace Bundle 和 Patch 路径都必须在声明根目录下解析。Build 拒绝 symlink 和运行态密钥文件。

Proposal 只能修改 `apps/<current-app-id>/`，必须先展示完整 Diff、执行 dry-run 并等待明确批准。它不能修改其他应用、Atelier Plugin、Builder、Reviewer、`.hermes-runtime`、`.atelier`、`.env` 或 Hermes 核心。

Project Defense 的 Source Profile 展示了更窄的能力边界：terminal、file、project 和 code-execution 工具组均禁用，专用只读 Plugin 会把每个请求路径解析到一个明确工作区以内。

## 进程与端点安全

每个 Profile 使用独立 loopback 端口和运行态 API Key。Atelier 在采纳、显示或终止已记录 PID 前，会验证该 PID 的命令行确实属于目标 `hermes -p <profile> gateway run`，避免 PID 复用导致误杀其他进程。

Gateway 启动后若健康检查失败，Atelier 会终止本次新建进程；Build 部分启动失败时会反向停止已经启动的 Profiles。无法完成清理时保留可管理的注册状态并明确报告，而不是丢失进程所有权。

## 失败语义

Trace Store 故障必须可见。Atelier 不会自动切换专家、伪造成功输出或实现业务重试。子 Run 超时会请求 Hermes 原生 stop，并报告 `child_timeout`；“停止请求已发送”不等于“已经停止”。

若调用授权或父子关联无法在 dispatch 前可靠写入，调用会直接失败。若下游已经启动后事件落盘降级，真实结果或错误仍会返回，同时标记 `trace_degraded`。
