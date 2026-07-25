"""Use one native Hermes Session for a two-turn Project Defense conversation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

base_url = os.environ.get("PROJECT_DEFENSE_BASE_URL", "http://127.0.0.1:19500").rstrip("/")
api_key = os.environ["PROJECT_DEFENSE_API_KEY"]
session_id = os.environ.get("PROJECT_DEFENSE_SESSION", "project-defense-client-example")
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def request(path: str, payload: dict[str, object]) -> dict[str, object]:
    call = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(call, timeout=180) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(exc.read().decode(errors="replace")) from exc


try:
    request("/api/sessions", {"id": session_id, "title": "Project Defense example"})
except SystemExit as exc:
    if "already exists" not in str(exc).lower() and "409" not in str(exc):
        raise

for message in [
    "我准备说这个队列把线上 p99 降低了 60%。请基于项目证据帮我完成答辩。",
    "请在不编造指标的前提下，补充架构取舍，并把表达收敛成 60 秒版本。",
]:
    result = request(f"/api/sessions/{session_id}/chat", {"message": message})
    print(json.dumps(result, indent=2, ensure_ascii=False))
