from __future__ import annotations

import json

import httpx
import pytest

from plugin.atelier.errors import AtelierError
from plugin.atelier.hermes_http import HermesHTTPClient


@pytest.mark.asyncio
async def test_parses_run_and_sse_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer local-secret"
        if request.url.path == "/v1/runs":
            body = json.loads(request.content)
            assert body["session_id"] == "at_" + "a" * 32 + "_root"
            assert request.headers["x-hermes-session-key"] == "stable-user"
            return httpx.Response(202, json={"run_id": "run_child", "status": "started"})
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=(
                    ': keepalive\n\ndata: {"event":"message.delta","delta":"hello"}\n\n'
                    'data: {"event":"run.completed","output":"done"}\n\n'
                ),
            )
        raise AssertionError(request.url.path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw_client:
        client = HermesHTTPClient("http://profile", "local-secret", client=raw_client)
        run_id = await client.start_run(
            task="work",
            session_id="at_" + "a" * 32 + "_root",
            memory_scope="stable-user",
        )
        events = [event async for event in client.events(run_id)]

    assert run_id == "run_child"
    assert [event["event"] for event in events] == ["message.delta", "run.completed"]


def test_rejects_invalid_sse_json() -> None:
    with pytest.raises(AtelierError, match="invalid SSE JSON"):
        HermesHTTPClient._parse_sse_line("data: not-json")
