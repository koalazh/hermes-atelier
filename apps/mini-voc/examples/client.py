"""Call a released Mini VOC entry Profile through Hermes' OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import urllib.request

base_url = os.environ.get("MINI_VOC_BASE_URL", "http://127.0.0.1:19300").rstrip("/")
api_key = os.environ["MINI_VOC_API_KEY"]
model = os.environ.get("MINI_VOC_MODEL", "support-demo--dispatcher")
payload = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": "登录验证码很晚，而且订单 ORD-1001 的退款状态是什么？",
        }
    ],
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions",
    data=json.dumps(payload, ensure_ascii=False).encode(),
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Hermes-Session-Id": "mini-voc-client-example",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=180) as response:
    print(json.dumps(json.loads(response.read()), indent=2, ensure_ascii=False))
