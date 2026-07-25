# 发布、安装与更新

## 发布

```bash
uv run atelier validate apps/mini-voc
uv run atelier cases apps/mini-voc
uv run atelier release apps/mini-voc /absolute/release/mini-voc --git-revision HEAD
```

目标目录必须不存在，Git Pack 必须已提交且与所选 commit/tag 一致。Release 复制可发布资产、按调用方注入独立 `profile_call`、生成可执行薄 wrapper `app` 和 `app.lock`，并在变换后哈希所有交付文件。接收方不需要安装 Atelier。

发布物可签名、压缩或提交到 Consumer 自己的 Git/制品系统；Atelier V2 不提供 Registry 或远程发布服务。

## Fresh 安装

```bash
cd /absolute/release/mini-voc
export HERMES_HOME=/absolute/fresh/hermes-home
export MODEL_API_KEY='set-in-consumer-shell'
export HERMES_APP_API_KEY='use-a-long-random-secret'

./app install --instance support-demo
./app configure \
  --instance support-demo \
  --model provider-model-name \
  --model-base-url https://provider.example/v1 \
  --model-key-env MODEL_API_KEY \
  --gateway-key-env HERMES_APP_API_KEY \
  --gateway-port 19300
./app start --instance support-demo
./app status --instance support-demo
./app attest --instance support-demo
./app cases --instance support-demo
```

`configure` 会把 Consumer 当前进程中的两个 Secret 写入每个 Profile 自己的 `.env`，权限设为 `0600`。命令行只传环境变量名，避免 Secret 进入 shell history。

唯一入口使用 `--gateway-port`，其余 Agent 再连续分配。只将唯一入口 Profile 端口加入 ingress；其他端口保持 loopback 和 API Key 认证。

安装前后的完整性校验以 `app.lock` 为根。Hermes 原生 install 会将 `distribution.yaml` 规范化为带物理 Profile 名、来源和安装时间的回执，configure 会改写 `config.yaml`；wrapper 只允许这两类明确的运行时变换，并把变换策略与结果 hash 写入实例 `runtime.json`。SOUL、Skills、Plugins 等资产始终必须直接匹配 release，`attest` 也会重新核验当前文件，不能用修改后的运行状态自我重设基线。

## 原生 Hermes 等价命令

Wrapper 不拥有生命周期。其关键动作等价于：

```bash
hermes -p default profile install profiles/dispatcher --name support-demo--dispatcher --yes --force
hermes -p support-demo--dispatcher config set model.default provider-model-name
hermes -p support-demo--dispatcher gateway start
hermes -p support-demo--dispatcher gateway status
hermes -p support-demo--dispatcher gateway stop
```

还需为每个 Profile 配置 Provider、`.env` 和 `local/app-runtime.json`。各 Pack 的 `INSTALL.md` 给出完整逐 Profile命令。Consumer 可完全不使用 `./app`，因此 wrapper 不是专有 Runtime。

## 调用

```bash
curl http://127.0.0.1:19300/v1/chat/completions \
  -H "Authorization: Bearer $HERMES_APP_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Session-Id: consumer-session-001' \
  -d '{"model":"support-demo--dispatcher","messages":[{"role":"user","content":"请处理这条反馈"}]}'
```

多轮对话使用同一个 Hermes Session ID 或先创建 `/api/sessions` 再调用 `/api/sessions/{id}/chat`。`/v1/runs` 的 `session_id` 不会自动加载 Chat 历史。

## 更新与回滚

```bash
cd /absolute/new-release
./app update --instance support-demo
```

更新过程：

1. 读取旧 `app.lock`、安装来源和运行配置；
2. 停止旧 Profile Gateways；
3. 安装/更新新 Distributions，删除新版本不再声明的物理 Profiles；
4. 重建逻辑映射并保留模型、端口和 Secret 环境变量配置；
5. 启动新 Gateways，以 `app.lock` 中首个 smoke Case 创建唯一 clean Session/Run，收集 Pack-local 临时 Trace，执行调用/输出断言和已声明的输出 Contract；
6. 成功后保存新安装状态。

失败时 wrapper 会停止新 Gateways，best-effort 重新安装旧 release、恢复旧 `app.lock`、映射和配置、重启旧服务并运行旧 smoke。外部进程、网络、模型和 Hermes 命令可能使回滚本身失败，因此该机制不宣称事务原子性；错误必须交给 Consumer 处理。

更新保留 Consumer 的 `.env`、Memory、Sessions 和 `local/`。`state_compatibility` 只给出迁移提示，不自动清理状态。

## 停止与卸载

```bash
./app stop --instance support-demo
```

停止只代理 Hermes Gateway stop，不删除 Profile 或状态。V2 当前不提供隐式 uninstall，以免误删 Consumer Memory/Session。需要卸载时先停止，再由 Consumer 显式执行 `hermes -p default profile delete <physical-profile> --yes` 并决定是否移除 `HERMES_HOME/app-packs/<instance>`。

## 发布门禁

发布前至少完成 Pack validate、Case parse、确定性测试、Ruff、build、Secret 扫描和 fresh `HERMES_HOME` 的 `attest`/`cases`。Case runner 独立于 Studio，执行后恢复运行映射并删除临时 Trace。真实模型 Case 只证明该次链路与断言，不证明生产质量或性能。
