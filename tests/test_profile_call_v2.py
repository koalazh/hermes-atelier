from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from plugin.profile_call import ProfileCaller, ProfileCallError


def write_runtime(path: Path, *, trace_url: str | None = None) -> None:
    payload = {
        "schema_version": 1,
        "instance": "support-dev",
        "current_agent": "dispatcher",
        "agents": {
            "dispatcher": {
                "profile": "support-dev--dispatcher",
                "base_url": "http://hermes/p/support-dev--dispatcher",
                "api_key_env": "PROFILE_CALL_API_KEY",
            },
            "product": {
                "profile": "support-dev--product",
                "base_url": "http://hermes/p/support-dev--product",
                "api_key_env": "PROFILE_CALL_API_KEY",
            },
        },
        "allowed_calls": {"dispatcher": ["product"]},
    }
    if trace_url:
        payload["trace"] = {"url": trace_url}
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_profile_call_works_without_atelier_session_or_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/v1/runs"):
            body = json.loads(request.content)
            assert body["session_id"].startswith("pc_")
            assert body["input"] == "Find product evidence"
            return httpx.Response(202, json={"run_id": "run-child"})
        if request.url.path.endswith("/v1/runs/run-child/events"):
            return httpx.Response(
                200,
                text='data: {"event":"run.completed","output":"PRD-17"}\n\n',
                headers={"content-type": "text/event-stream"},
            )
        raise AssertionError(request.url)

    caller = ProfileCaller(runtime_path=runtime, transport=httpx.MockTransport(handler))
    result = await caller.call(
        {"target": "product", "task": "Find product evidence"},
        source_session_id="ordinary-hermes-session",
    )

    assert result == {
        "ok": True,
        "target": "product",
        "target_profile": "support-dev--product",
        "result": "PRD-17",
        "source_session_id": "ordinary-hermes-session",
        "target_session_id": result["target_session_id"],
        "target_hermes_run_id": "run-child",
        "call_id": result["call_id"],
        "trace_degraded": False,
    }
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_trace_sink_failure_does_not_break_business_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime, trace_url="http://trace/events")
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "trace":
            return httpx.Response(503, text="offline")
        if request.url.path.endswith("/v1/runs"):
            return httpx.Response(202, json={"run_id": "run-child"})
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                text='data: {"event":"run.completed","output":"usable result"}\n\n',
            )
        raise AssertionError(request.url)

    caller = ProfileCaller(runtime_path=runtime, transport=httpx.MockTransport(handler))
    result = await caller.call({"target": "product", "task": "Work"})

    assert result["ok"] is True
    assert result["result"] == "usable result"
    assert result["trace_degraded"] is True


@pytest.mark.asyncio
async def test_retained_scope_is_hashed_into_target_session_without_leaking_raw_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/runs"):
            captured.update(json.loads(request.content))
            captured["scope_header"] = request.headers.get("X-Hermes-Session-Key")
            return httpx.Response(202, json={"run_id": "run-retained"})
        return httpx.Response(200, text='data: {"event":"run.completed","output":"ok"}\n\n')

    result = await ProfileCaller(
        runtime_path=runtime, transport=httpx.MockTransport(handler)
    ).call(
        {
            "target": "product",
            "task": "Retained work",
            "memory_scope": "candidate-private-scope",
        }
    )

    assert str(captured["session_id"]).startswith(f"pcms_{result['memory_scope_id']}_")
    assert captured["scope_header"] == "candidate-private-scope"
    assert "candidate-private-scope" not in str(captured["session_id"])


@pytest.mark.asyncio
async def test_profile_call_enforces_logical_allowed_calls(tmp_path: Path) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    caller = ProfileCaller(runtime_path=runtime)

    with pytest.raises(ProfileCallError, match="not allowed"):
        await caller.call({"target": "dispatcher", "task": "Loop"})
