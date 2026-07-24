# ADR 006：项目本地 HERMES_HOME

状态：已接受

所有 Atelier 子进程使用绝对 `<repo>/.hermes-runtime` 作为 `HERMES_HOME`，并显式指定 `-p <profile>`。Distribution 源码留在 Git；运行态 Memory、Sessions、凭据、日志和状态禁止提交。

删除仓库即可清理完整开发环境，但该边界只是 Hermes 状态隔离，不是操作系统安全沙箱。
