# ADR 006：项目本地 HERMES_HOME

状态：V1 开发环境约定；V2 Consumer 自主选择 HERMES_HOME

V1 统一使用 `<repo>/.hermes-runtime`。V2 App Pack 接收方必须显式选择绝对 `HERMES_HOME`；Studio 的 Builder/Drafter/Reviewer 也由开发者按 Hermes 原生命令管理。Distribution 源码留在 Git；运行态 Memory、Sessions、凭据、日志和状态禁止提交。

`HERMES_HOME` 边界只是 Hermes 状态隔离，不是操作系统安全沙箱。
