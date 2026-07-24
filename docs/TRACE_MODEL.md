# Trace 数据模型

## 三种不同作用域

- **Hermes Session**：属于单个 Profile，保存该 Agent 的 transcript。
- **Hermes Run**：属于单个 Profile 的一次执行。
- **Atelier Run**：一次多 Profile 应用调用的关联信封，不合并 transcript，也不替代 Hermes 状态。

随机 Atelier Run ID 只用于一次 transcript 关联。需要稳定长期 Memory 时，使用独立的 `X-Hermes-Session-Key` 业务作用域，不能把 Atelier Run ID 当作长期记忆 Key。

## 核心实体

Atelier 只保留五个核心实体：

- `AtelierApp`：版本化应用注册；
- `AtelierRun`：一次应用级调用；
- `AtelierSpan`：一次被观测的跨 Profile 调用；
- `AtelierEvent`：执行期间规范化、脱敏后的必要事件；
- `AtelierReview`：针对一个或多个 Runs 的证据化评审。

Endpoint、Build、Feedback 和 Proposal 行只支撑运行与批准闭环，不构成另一套 Agent Runtime。

## Session ID 与父子关联

Root Session ID 使用：

```text
at_<32-hex-run-id>_root
```

Child Session ID 使用：

```text
at_<run-id>_<32-hex-span-id>
```

解析器只接受以上格式，并进一步校验数据库中记录的来源 Profile、父 Span 和来源 Session。自然语言中的 Profile 或 Run ID 声明不具备可信身份。

## 事件采集

Hermes 终态 Run 记录只有限期保留，因此 Atelier 在 Run 执行期间持续消费 SSE。事件脱敏后只写入一次 SQLite，不维护后台 JSONL 镜像。

主动导出时才创建冻结 Trace Bundle：

```text
manifest.json
events.jsonl
sessions/
feedback.json
app-definition/
result.md
```

Bundle 只获取本次 Review 引用的 Sessions，不复制完整 Memory、密钥、环境变量、无关 Session 或工作目录内容。

## 降级与停止

如果下游调用开始后事件持久化失败，Atelier 返回真实下游结果并标记 `trace_degraded`。如果授权或父子关系在 dispatch 前无法可靠建立，则调用失败关闭。

Hermes stop 响应只代表请求已发送；只有后续 terminal event/status 才能证明 Run 已取消。Atelier 不把 `stopping` 误报为 `cancelled`。
