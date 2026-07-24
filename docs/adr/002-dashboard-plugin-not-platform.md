# ADR 002：Dashboard Plugin，而非平台

状态：已接受

Atelier 作为一个可信 Hermes Plugin 交付，同时包含 Dashboard Tab、本地 routes、工具和 CLI。它不提供常驻服务、公共部署模式、租户模型或重复管理页面。

业务 Profile Gateways 独立于 Dashboard 运行；停止 Dashboard 不会停止已经启动的业务 Agents。
