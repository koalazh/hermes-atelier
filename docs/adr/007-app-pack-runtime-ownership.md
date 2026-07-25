# ADR 007：App Pack 与 Hermes 拥有应用 Runtime

状态：已接受

V2 发布应用由 App Pack 描述逻辑 Agent、Distribution、唯一公开入口、权限、状态策略、Cases 和 Contracts；安装后 Hermes 拥有 Profile、Gateway、Session、Run、Memory、Plugin 和进程生命周期。

Atelier 不维护 Endpoint/PID Registry、Root Run、后台 supervisor 或应用状态数据库。跨 Profile HTTP 使用可随 Pack 发布的独立 `profile_call`，Trace Sink 可选且失败不改变已经成功的业务结果。

当前 Hermes multiplex 不能隔离 Profile 私有 Plugins，因此 wrapper 为每个物理 Profile 代理一个原生 loopback Gateway。该限制消失后应收缩 wrapper，不维持平行实现。
