from __future__ import annotations

import json
from pathlib import Path

from plugin.atelier.store import AtelierStore


def registered_store(tmp_path: Path) -> AtelierStore:
    store = AtelierStore(tmp_path / "atelier.db")
    store.upsert_app(
        app_id="sample-app",
        display_name="Sample App",
        entry_profile="sample-app--entry",
        source_path=str(tmp_path / "sample-app"),
        definition_revision="abc123",
        definition={
            "schema_version": 1,
            "id": "sample-app",
            "display_name": "Sample App",
            "entry_profile": "sample-app--entry",
            "profiles": [],
        },
    )
    return store


def test_run_span_event_round_trip(tmp_path: Path) -> None:
    store = registered_store(tmp_path)
    run = store.create_run(
        app_id="sample-app",
        scenario_id="smoke",
        root_profile="sample-app--entry",
        definition_revision="abc123",
        input_text="Investigate",
        memory_scope=None,
        user_label="demo",
    )
    span = store.create_span(
        atelier_run_id=run["id"],
        parent_span_id=None,
        source_profile="sample-app--entry",
        target_profile="sample-app--expert",
        source_session_id=run["root_session_id"],
        request_summary="Inspect the evidence",
    )
    store.update_span(span["id"], status="running", target_hermes_run_id="run_child")
    event_id = store.add_event(
        atelier_run_id=run["id"],
        span_id=span["id"],
        profile="sample-app--expert",
        hermes_run_id="run_child",
        event_type="message.delta",
        timestamp=123.5,
        payload={"delta": "safe", "Authorization": "Bearer top-secret"},
    )

    events = store.list_events(run["id"])

    assert event_id == events[0]["id"]
    assert events[0]["payload"]["Authorization"] == "[REDACTED]"
    assert store.find_span_by_session(span["target_session_id"])["id"] == span["id"]
    assert store.list_spans(run["id"])[0]["target_hermes_run_id"] == "run_child"


def test_app_upsert_preserves_created_at(tmp_path: Path) -> None:
    store = registered_store(tmp_path)
    first = store.get_app("sample-app")
    store.upsert_app(
        app_id="sample-app",
        display_name="Renamed",
        entry_profile="sample-app--entry",
        source_path="/tmp/sample-app",
        definition_revision="next",
        definition={"id": "sample-app"},
    )
    second = store.get_app("sample-app")

    assert second["display_name"] == "Renamed"
    assert second["created_at"] == first["created_at"]
    assert json.loads(second["definition_json"])["id"] == "sample-app"


def test_endpoint_never_contains_key_column(tmp_path: Path) -> None:
    store = registered_store(tmp_path)
    endpoint = store.set_endpoint(
        profile="sample-app--entry",
        app_id="sample-app",
        host="127.0.0.1",
        port=18100,
    )

    assert endpoint["host"] == "127.0.0.1"
    assert not any("key" in column.lower() or "secret" in column.lower() for column in endpoint)
