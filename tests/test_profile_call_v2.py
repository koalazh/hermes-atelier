from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest

from plugin.profile_call import ProfileCaller, ProfileCallError


def write_runtime(
    path: Path, *, trace_url: str | None = None, trace_file: Path | None = None
) -> None:
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
    if trace_file:
        payload["trace"] = {"file": str(trace_file)}
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
async def test_slow_trace_sink_uses_short_independent_timeout_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime, trace_url="http://trace/events")
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")
    dispatched_at: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "trace":
            await asyncio.sleep(1)
            return httpx.Response(202)
        if request.url.path.endswith("/v1/runs"):
            dispatched_at.append(time.monotonic())
            return httpx.Response(202, json={"run_id": "run-child"})
        return httpx.Response(
            200,
            text='data: {"event":"run.completed","output":"usable result"}\n\n',
        )

    started_at = time.monotonic()
    result = await ProfileCaller(
        runtime_path=runtime,
        transport=httpx.MockTransport(handler),
        trace_timeout=0.02,
    ).call({"target": "product", "task": "Work"})

    assert dispatched_at[0] - started_at < 0.2
    assert result["ok"] is True
    assert result["trace_degraded"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stop_response", "expected"),
    [
        (httpx.Response(202, json={"status": "stopping"}), "stop_requested"),
        (httpx.Response(200, json={"status": "cancelled"}), "stop_confirmed"),
        (httpx.Response(503), "stop_unknown"),
    ],
)
async def test_event_failure_best_effort_stops_child_run_with_honest_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop_response: httpx.Response,
    expected: str,
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/v1/runs"):
            return httpx.Response(202, json={"run_id": "run-orphan"})
        if request.url.path.endswith("/events"):
            return httpx.Response(200, text="data: not-json\n\n")
        if request.url.path.endswith("/stop"):
            return stop_response
        raise AssertionError(request.url)

    with pytest.raises(ProfileCallError) as raised:
        await ProfileCaller(
            runtime_path=runtime,
            transport=httpx.MockTransport(handler),
        ).call({"target": "product", "task": "Work"})

    assert raised.value.stop_status == expected
    assert requests[-1] == "/p/support-dev--product/v1/runs/run-orphan/stop"


@pytest.mark.asyncio
async def test_caller_cancellation_requests_child_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")
    stream_started = asyncio.Event()
    stop_requested = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/runs"):
            return httpx.Response(202, json={"run_id": "run-cancelled-caller"})
        if request.url.path.endswith("/events"):
            stream_started.set()
            await asyncio.Event().wait()
        if request.url.path.endswith("/stop"):
            stop_requested.set()
            return httpx.Response(202, json={"status": "stopping"})
        raise AssertionError(request.url)

    task = asyncio.create_task(
        ProfileCaller(
            runtime_path=runtime,
            transport=httpx.MockTransport(handler),
        ).call({"target": "product", "task": "Work"})
    )
    await stream_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(stop_requested.wait(), timeout=1)


@pytest.mark.asyncio
async def test_total_deadline_stops_child_even_when_sse_keeps_streaming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")
    stop_requested = asyncio.Event()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(0.2)
                yield b'data: {"event":"message.delta","delta":"still working"}\n\n'

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/runs"):
            return httpx.Response(202, json={"run_id": "run-streaming"})
        if request.url.path.endswith("/events"):
            return httpx.Response(200, stream=SlowStream())
        if request.url.path.endswith("/stop"):
            stop_requested.set()
            return httpx.Response(202, json={"status": "stopping"})
        raise AssertionError(request.url)

    with pytest.raises(ProfileCallError) as raised:
        await ProfileCaller(
            runtime_path=runtime,
            transport=httpx.MockTransport(handler),
        ).call({"target": "product", "task": "Work", "timeout_seconds": 1})

    assert raised.value.stop_status == "stop_requested"
    assert stop_requested.is_set()


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


@pytest.mark.asyncio
async def test_profile_call_can_emit_pack_local_case_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    trace_file = tmp_path / "case-run.jsonl"
    write_runtime(runtime, trace_file=trace_file)
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/runs"):
            return httpx.Response(202, json={"run_id": "run-child"})
        return httpx.Response(200, text='data: {"event":"run.completed","output":"ok"}\n\n')

    result = await ProfileCaller(
        runtime_path=runtime, transport=httpx.MockTransport(handler)
    ).call(
        {"target": "product", "task": "Work"},
        source_session_id="pack_case_smoke_123",
    )
    traces = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]

    assert result["trace_degraded"] is False
    assert [event["event"] for event in traces] == [
        "profile_call.started",
        "profile_call.completed",
    ]
    assert all(event["source_session_id"] == "pack_case_smoke_123" for event in traces)


@pytest.mark.asyncio
async def test_profile_call_writes_session_partitioned_trace_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "local" / "app-runtime.json"
    write_runtime(runtime)
    mapping = json.loads(runtime.read_text(encoding="utf-8"))
    trace_directory = tmp_path / "call-traces"
    mapping["trace"] = {"directory": str(trace_directory)}
    runtime.write_text(json.dumps(mapping), encoding="utf-8")
    monkeypatch.setenv("PROFILE_CALL_API_KEY", "runtime-only-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/runs"):
            return httpx.Response(202, json={"run_id": "run-child"})
        return httpx.Response(200, text='data: {"event":"run.completed","output":"ok"}\n\n')

    await ProfileCaller(
        runtime_path=runtime, transport=httpx.MockTransport(handler)
    ).call(
        {"target": "product", "task": "Work"},
        source_session_id="pack_case_smoke_123",
    )

    files = list(trace_directory.glob("*.jsonl"))
    assert len(files) == 1
    events = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert [event["event"] for event in events] == [
        "profile_call.started",
        "profile_call.completed",
    ]
