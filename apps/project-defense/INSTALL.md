# Project Defense 安装

## 使用薄 wrapper

```bash
uv run atelier release apps/project-defense /absolute/release/project-defense --git-revision HEAD
cd /absolute/release/project-defense
export HERMES_HOME=/absolute/fresh/hermes-home
export MODEL_API_KEY='set-in-your-shell'
export HERMES_APP_API_KEY='use-a-long-random-secret'

./app install --instance defense-demo
./app configure \
  --instance defense-demo \
  --model provider-model-name \
  --model-base-url https://provider.example/v1 \
  --model-key-env MODEL_API_KEY \
  --gateway-key-env HERMES_APP_API_KEY \
  --gateway-port 19500
./app start --instance defense-demo
./app status --instance defense-demo
./app attest --instance defense-demo
./app live-probe --instance defense-demo
./app cases --instance defense-demo
```

Profiles 为 `defense-demo--host`、`--source`、`--architecture`、`--coach`，端口为 19500–19503。只将 19500 入口加入 ingress。

## 不使用 wrapper

```bash
hermes -p default profile install profiles/host --name defense-demo--host --yes --force
hermes -p default profile install profiles/source --name defense-demo--source --yes --force
hermes -p default profile install profiles/architecture --name defense-demo--architecture --yes --force
hermes -p default profile install profiles/coach --name defense-demo--coach --yes --force

for profile in defense-demo--host defense-demo--source defense-demo--architecture defense-demo--coach; do
  hermes -p "$profile" config set model.default provider-model-name
  hermes -p "$profile" config set model.provider custom:app_pack
  hermes -p "$profile" config set providers.app_pack.api https://provider.example/v1 --force
  hermes -p "$profile" config set providers.app_pack.key_env MODEL_API_KEY --force
done
```

为四个 Profile 分别创建权限 `0600` 的 `.env`，设置 loopback host、连续端口、各目标独立 Gateway Key，并只向 host 注入允许目标的 Key；运行 mapping 也只包含 self 和允许目标。release 中 host Distribution 必须包含 `plugins/profile_call`。最后分别执行 `hermes -p <physical-profile> gateway start`。

wrapper 配置的是便利默认模型；Consumer 可用 Hermes 原生命令逐 Profile 覆盖。configured attestation 记录 config hash，live probe 报告各 Gateway 当前可观察模型。

Source 的 `sample-source/` 和窄只读 Plugin 属于 Distribution，不需要宿主工程路径环境变量。

## 多轮与长期状态

普通多轮对话复用 Hermes Session ID。只有确实需要稳定表达偏好时，Consumer 或上游 Agent 才选择明确 `memory_scope`；Host 会把它传给 Coach，`profile_call` 生成不含原文的派生 scope ID，Coach 将偏好写入自身 `local/`。不要把临时 Session ID 当长期 scope，也不要使用 Hermes 全局 User Profile 代替 caller isolation。

## 更新与停止

```bash
./app update --instance defense-demo
./app stop --instance defense-demo
```

该 Pack 标记 `review_required`。更新是 local、best-effort、experimental；先评估 caller-scoped Memory，必要时选择新 scope，wrapper 不会删除它。保留旧 release，语义见仓库 [`docs/RELEASE.md`](../../docs/RELEASE.md)。
