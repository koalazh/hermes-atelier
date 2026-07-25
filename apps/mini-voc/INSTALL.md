# Mini VOC 安装

## 使用薄 wrapper

先在 Atelier 源码仓库创建 release；示例源码目录本身不包含生成的 `app.lock` 和 `app`：

```bash
uv run atelier release apps/mini-voc /absolute/release/mini-voc --git-revision HEAD
cd /absolute/release/mini-voc
export HERMES_HOME=/absolute/fresh/hermes-home
export MODEL_API_KEY='set-in-your-shell'
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
```

物理 Profiles 为 `support-demo--dispatcher`、`support-demo--product` 和 `support-demo--transaction`，端口依次为 19300–19302。只将 19300 入口加入 ingress。

停止：

```bash
./app stop --instance support-demo
```

## 不使用 wrapper

Wrapper 只是以下 Hermes 原生操作和运行映射生成的便利层：

```bash
hermes -p default profile install profiles/dispatcher --name support-demo--dispatcher --yes --force
hermes -p default profile install profiles/product --name support-demo--product --yes --force
hermes -p default profile install profiles/transaction --name support-demo--transaction --yes --force

for profile in support-demo--dispatcher support-demo--product support-demo--transaction; do
  hermes -p "$profile" config set model.default provider-model-name
  hermes -p "$profile" config set model.provider custom:app_pack
  hermes -p "$profile" config set providers.app_pack.api https://provider.example/v1 --force
  hermes -p "$profile" config set providers.app_pack.key_env MODEL_API_KEY --force
done
```

随后为每个 Profile 创建权限 `0600` 的 `.env`，配置 `MODEL_API_KEY`、`API_SERVER_KEY`、`API_SERVER_HOST=127.0.0.1` 和各自端口；在 `local/app-runtime.json` 中写逻辑映射、`current_agent` 与 `allowed_calls`，再执行：

```bash
hermes -p support-demo--dispatcher gateway start
hermes -p support-demo--product gateway start
hermes -p support-demo--transaction gateway start
```

原生安装必须保证 release 中 dispatcher Distribution 已包含 `plugins/profile_call`。推荐用 `./app configure` 避免手工映射错误，但应用 Runtime 不依赖 wrapper 常驻。

## 更新

在新 release 目录中执行 `./app update --instance support-demo`。更新保留 `.env`、Memory、Sessions 和 `local/`，重启后运行首个 smoke Case；失败时 best-effort 恢复旧 release。保留旧 release 目录以支持回滚。
