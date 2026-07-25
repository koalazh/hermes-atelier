# Mini VOC V2 App Pack

Mini VOC 是一个完全模拟的客户反馈分诊示例。公开入口 `dispatcher` 自主决定是否调用内部 `product`、`transaction` 或两者；Atelier 核心没有任何 VOC 路由。

模拟工具只返回 Pack 内置记录：Product 提供问题归属、已知记录和计划；Transaction 提供示例订单与退款状态。所有回答都应把模拟记录与生产事实区分。该 Pack 不连接真实工单、订单或监控系统。

## 状态

`state_policy: session_only`：同一个 Hermes Session 可多轮延续，但 Pack 不声明跨 Session 长期 Memory。更新兼容性为 `preserve`。

## 使用

先按 [安装说明](INSTALL.md) 发布和启动，再运行：

```bash
MINI_VOC_BASE_URL=http://127.0.0.1:19300 \
MINI_VOC_API_KEY="$HERMES_APP_API_KEY" \
python examples/client.py
```

Cases 覆盖模糊输入不调用专家、单领域、跨领域和专家失败。公开回答使用“已知 / 不确定 / 下一步”的半结构化语义约束；Hermes 0.19 的主 Agent Run 接口不提供可由 Pack 声明的结构化响应参数，因此本示例不虚假承诺 JSON Schema。

## 边界

这是开发回归应用，不是生产客服系统。真实模型输出可能变化；Case 和 smoke 证明协议与约束，不证明业务正确率。
