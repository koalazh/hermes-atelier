from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .errors import AtelierError


class HermesHTTPClient:
    def __init__(self, base_url: str, api_key: str, *, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client

    async def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> httpx.Response:
        if self._client is not None:
            response = await self._client.request(
                method, f"{self.base_url}{path}", headers=self._headers, json=json_body
            )
        else:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method, f"{self.base_url}{path}", headers=self._headers, json=json_body
                )
        return response

    async def start_run(
        self,
        *,
        task: str,
        session_id: str,
        memory_scope: str | None = None,
        instructions: str | None = None,
    ) -> str:
        headers = dict(self._headers)
        if memory_scope:
            headers["X-Hermes-Session-Key"] = memory_scope
        body: dict[str, Any] = {"input": task, "session_id": session_id}
        if instructions:
            body["instructions"] = instructions
        if self._client is not None:
            response = await self._client.post(
                f"{self.base_url}/v1/runs", headers=headers, json=body
            )
        else:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(f"{self.base_url}/v1/runs", headers=headers, json=body)
        if response.status_code != 202:
            raise AtelierError(
                "child_call_failed",
                f"Hermes rejected run start with HTTP {response.status_code}",
                {"response": response.text[:1000]},
            )
        payload = response.json()
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not run_id.startswith("run_"):
            raise AtelierError("child_call_failed", "Hermes returned an invalid run id")
        return run_id

    async def events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        url = f"{self.base_url}/v1/runs/{run_id}/events"
        if self._client is not None:
            async with self._client.stream("GET", url, headers=self._headers) as response:
                if response.status_code != 200:
                    raise AtelierError(
                        "trace_degraded",
                        f"Hermes SSE returned HTTP {response.status_code}",
                    )
                async for line in response.aiter_lines():
                    event = self._parse_sse_line(line)
                    if event is not None:
                        yield event
            return
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=self._headers) as response:
                if response.status_code != 200:
                    raise AtelierError(
                        "trace_degraded",
                        f"Hermes SSE returned HTTP {response.status_code}",
                    )
                async for line in response.aiter_lines():
                    event = self._parse_sse_line(line)
                    if event is not None:
                        yield event

    async def status(self, run_id: str) -> dict[str, Any]:
        response = await self._request("GET", f"/v1/runs/{run_id}")
        if response.status_code != 200:
            raise AtelierError(
                "child_call_failed", f"Hermes run status returned HTTP {response.status_code}"
            )
        return response.json()

    async def stop(self, run_id: str) -> dict[str, Any]:
        response = await self._request("POST", f"/v1/runs/{run_id}/stop", json_body={})
        if response.status_code not in {200, 202, 404}:
            raise AtelierError(
                "child_cancelled", f"Hermes stop returned HTTP {response.status_code}"
            )
        return response.json()

    async def session_messages(self, session_id: str) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/api/sessions/{session_id}/messages")
        if response.status_code != 200:
            raise AtelierError(
                "trace_degraded",
                f"Hermes session messages returned HTTP {response.status_code}",
            )
        payload = response.json()
        if isinstance(payload, list):
            return payload
        messages = payload.get("messages", []) if isinstance(payload, dict) else []
        return messages if isinstance(messages, list) else []

    async def health(self) -> dict[str, Any]:
        response = await self._request("GET", "/health")
        if response.status_code != 200:
            raise AtelierError("profile_unhealthy", f"health returned HTTP {response.status_code}")
        return response.json()

    @staticmethod
    def _parse_sse_line(line: str) -> dict[str, Any] | None:
        if not line.startswith("data:"):
            return None
        raw = line[5:].strip()
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AtelierError("trace_degraded", "Hermes emitted invalid SSE JSON") from exc
        if not isinstance(value, dict):
            raise AtelierError("trace_degraded", "Hermes emitted a non-object SSE event")
        return value
