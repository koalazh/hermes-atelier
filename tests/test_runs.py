from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from plugin.atelier.services.runs import RunService, parse_atelier_session
from plugin.atelier.store import AtelierStore

DEFINITION = {
    "schema_version": 1,
    "id": "sample-app",
    "display_name": "Sample App",
    "entry_profile": "sample-app--entry",
    "profiles": [
        {"name": "sample-app--entry", "source": "profiles/entry"},
        {"name": "sample-app--expert", "source": "profiles/expert"},
        {"name": "sample-app--second", "source": "profiles/second"},
    ],
    "allowed_calls": {
        "sample-app--entry": ["sample-app--expert"],
        "sample-app--expert": ["sample-app--second"],
    },
    "scenarios_dir": "scenarios",
}


class StubProfiles:
    def endpoint_credentials(self, profile: str) -> tuple[str, str]:
        return f"http://{profile}", "runtime-secret"


class FakeHermesClient:
    starts: list[dict[str, Any]] = []
    stopped: list[str] = []
    mode = "completed"

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def start_run(self, **kwargs: Any) -> str:
        self.starts.append({"base_url": self.base_url, **kwargs})
        return f"run_{len(self.starts)}"

    async def events(self, run_id: str):
        yield {"event": "message.delta", "timestamp": 1, "delta": "working"}
        if self.mode == "timeout":
            await asyncio.sleep(1)
            return
        if self.mode == "failed":
            yield {"event": "run.failed", "timestamp": 2, "error": "expert failed"}
        else:
            yield {"event": "run.completed", "timestamp": 2, "output": "real result"}

    async def status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed", "output": "polled result"}

    async def stop(self, run_id: str) -> dict[str, Any]:
        self.stopped.append(run_id)
        return {"run_id": run_id, "status": "stopping"}


def make_service(tmp_path: Path) -> tuple[RunService, AtelierStore, dict[str, Any]]:
    FakeHermesClient.starts = []
    FakeHermesClient.stopped = []
    FakeHermesClient.mode = "completed"
    store = AtelierStore(tmp_path / "atelier.db")
    store.upsert_app(
        app_id="sample-app",
        display_name="Sample App",
        entry_profile="sample-app--entry",
        source_path=str(tmp_path / "sample-app"),
        definition_revision="rev1",
        definition=DEFINITION,
    )
    run = store.create_run(
        app_id="sample-app",
        scenario_id="smoke",
        root_profile="sample-app--entry",
        definition_revision="rev1",
        input_text="root request",
        memory_scope=None,
        user_label=None,
    )
    service = RunService(
        store,
        profile_service=StubProfiles(),  # type: ignore[arg-type]
        client_factory=FakeHermesClient,
    )
    return service, store, run


def test_parse_atelier_session() -> None:
    run_id = "a" * 32
    assert parse_atelier_session(f"at_{run_id}_root") == (run_id, None)
    assert parse_atelier_session(f"at_{run_id}_{'b' * 32}") == (run_id, "b" * 32)


@pytest.mark.asyncio
async def test_child_call_records_real_run_and_events(tmp_path: Path) -> None:
    service, store, run = make_service(tmp_path)

    result = await service.call(
        {"target": "sample-app--expert", "task": "inspect evidence"},
        source_profile="sample-app--entry",
        task_id=run["root_session_id"],
        session_id=run["root_session_id"],
    )

    assert result["ok"] is True
    assert result["result"] == "real result"
    assert result["target_hermes_run_id"] == "run_1"
    spans = store.list_spans(run["id"])
    assert spans[0]["source_session_id"] == run["root_session_id"]
    assert spans[0]["target_hermes_run_id"] == "run_1"
    assert [event["event_type"] for event in store.list_events(run["id"])] == [
        "message.delta",
        "run.completed",
    ]


@pytest.mark.asyncio
async def test_multilevel_call_uses_parent_span(tmp_path: Path) -> None:
    service, store, run = make_service(tmp_path)
    first = await service.call(
        {"target": "sample-app--expert", "task": "first"},
        source_profile="sample-app--entry",
        task_id=run["root_session_id"],
        session_id=run["root_session_id"],
    )

    second = await service.call(
        {"target": "sample-app--second", "task": "second"},
        source_profile="sample-app--expert",
        task_id=first["target_session_id"],
        session_id=first["target_session_id"],
    )

    assert second["ok"] is True
    spans = store.list_spans(run["id"])
    assert spans[1]["parent_span_id"] == spans[0]["id"]


@pytest.mark.asyncio
async def test_rejects_disallowed_target_before_dispatch(tmp_path: Path) -> None:
    service, store, run = make_service(tmp_path)

    result = await service.call(
        {"target": "sample-app--second", "task": "bypass allowlist"},
        source_profile="sample-app--entry",
        task_id=run["root_session_id"],
        session_id=run["root_session_id"],
    )

    assert result["error_type"] == "call_not_allowed"
    assert FakeHermesClient.starts == []
    assert store.list_spans(run["id"]) == []


@pytest.mark.asyncio
async def test_rejects_missing_dispatch_context(tmp_path: Path) -> None:
    service, _store, run = make_service(tmp_path)

    result = await service.call(
        {"target": "sample-app--expert", "task": "work"},
        source_profile="sample-app--entry",
        task_id="",
        session_id=run["root_session_id"],
    )

    assert result["error_type"] == "incompatible_hermes"


@pytest.mark.asyncio
async def test_child_failure_returns_real_error(tmp_path: Path) -> None:
    service, store, run = make_service(tmp_path)
    FakeHermesClient.mode = "failed"

    result = await service.call(
        {"target": "sample-app--expert", "task": "fail"},
        source_profile="sample-app--entry",
        task_id=run["root_session_id"],
        session_id=run["root_session_id"],
    )

    assert result["error_type"] == "child_call_failed"
    assert store.list_spans(run["id"])[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_child_timeout_requests_stop(tmp_path: Path) -> None:
    service, store, run = make_service(tmp_path)
    FakeHermesClient.mode = "timeout"

    result = await service.call(
        {"target": "sample-app--expert", "task": "slow", "timeout_seconds": 1},
        source_profile="sample-app--entry",
        task_id=run["root_session_id"],
        session_id=run["root_session_id"],
    )

    assert result["error_type"] == "child_timeout"
    assert FakeHermesClient.stopped == ["run_1"]
    assert store.list_spans(run["id"])[0]["status"] == "timeout"


@pytest.mark.asyncio
async def test_event_store_failure_marks_trace_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, store, run = make_service(tmp_path)
    monkeypatch.setattr(store, "add_event", lambda **_kwargs: (_ for _ in ()).throw(OSError("db")))

    result = await service.call(
        {"target": "sample-app--expert", "task": "work"},
        source_profile="sample-app--entry",
        task_id=run["root_session_id"],
        session_id=run["root_session_id"],
    )

    assert result["ok"] is True
    assert result["result"] == "real result"
    assert result["trace_degraded"] is True
    assert store.list_spans(run["id"])[0]["error_type"] == "trace_degraded"


@pytest.mark.asyncio
async def test_root_run_uses_entry_profile_and_session(tmp_path: Path) -> None:
    service, store, run = make_service(tmp_path)

    result = await service.execute_root(run["id"])

    assert result["status"] == "completed"
    assert FakeHermesClient.starts[0]["session_id"] == run["root_session_id"]
    assert FakeHermesClient.starts[0]["base_url"] == "http://sample-app--entry"
    assert store.list_events(run["id"])[-1]["event_type"] == "run.completed"
