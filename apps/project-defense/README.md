# Project Defense V2 App Pack

Project Defense 是源码证据约束的项目答辩练习应用。公开入口 `host` 按需调用：

- `source`：只读 Pack 内置的示例源码工作区；
- `architecture`：讨论取舍，不能虚构源码事实；
- `coach`：收敛表达、所有权和不确定性，可使用显式长期 Memory scope。

该示例不读取用户任意仓库。`source` 的样例工程随 Distribution 发布，工具访问路径被限制在该目录内。

## 状态

`state_policy: caller_scoped`：Consumer 必须显式选择长期 scope。更新兼容性为 `review_required`，wrapper 不会自动重置 Memory 或 Sessions。

## 使用

先按 [安装说明](INSTALL.md) 启动，然后：

```bash
PROJECT_DEFENSE_BASE_URL=http://127.0.0.1:19500 \
PROJECT_DEFENSE_API_KEY="$HERMES_APP_API_KEY" \
python examples/client.py
```

示例客户端用同一个原生 Hermes Session 发送两轮消息，以验证真实多轮对话。

## 证据边界

Pack 中没有线上 p99 测量。面对“降低 60%”之类主张，应用应调用 Source 并拒绝无来源数字。真实模型仍可能出错，输出必须由开发者复核。
