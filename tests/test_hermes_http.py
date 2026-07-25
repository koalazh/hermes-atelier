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


@pytest.mark.asyncio
async def test_uses_native_session_create_and_chat_for_multiturn() -> None:
    requests: list[tuple[str, str, dict]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        requests.append((request.method, request.url.path, body))
        if request.url.path == "/api/sessions":
            return httpx.Response(201, json={"session": {"id": body["id"]}})
        if request.url.path.endswith("/chat"):
            return httpx.Response(
                200,
                json={
                    "session_id": "design-session",
                    "message": {"role": "assistant", "content": "PLAN_READY"},
                },
            )
        raise AssertionError(request.url.path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw_client:
        client = HermesHTTPClient("http://profile", "local-secret", client=raw_client)
        await client.ensure_session("design-session", title="Design")
        result = await client.chat_session(
            "design-session", message="continue", instructions="planning only"
        )

    assert result["message"]["content"] == "PLAN_READY"
    assert requests == [
        (
            "POST",
            "/api/sessions",
            {"id": "design-session", "title": "Design"},
        ),
        (
            "POST",
            "/api/sessions/design-session/chat",
            {"message": "continue", "instructions": "planning only"},
        ),
    ]


@pytest.mark.asyncio
async def test_lists_native_sessions_without_reimplementing_session_state() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/sessions"
        assert request.url.params["limit"] == "7"
        return httpx.Response(
            200,
            json={"sessions": [{"id": "recent-session", "title": "Recent"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw_client:
        client = HermesHTTPClient("http://profile", "local-secret", client=raw_client)
        sessions = await client.sessions(limit=7)

    assert sessions == [{"id": "recent-session", "title": "Recent"}]
