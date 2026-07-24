from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from plugin.atelier.errors import AtelierError
from plugin.atelier.services.reviews import REQUIRED_REVIEW_HEADINGS, ReviewService
from plugin.atelier.store import AtelierStore


class StubProfiles:
    def endpoint_credentials(self, profile: str) -> tuple[str, str]:
        return f"http://{profile}", "secret"


class SessionClient:
    def __init__(self, base_url: str, key: str):
        self.base_url = base_url

    async def session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return [{"role": "user", "content": session_id, "Authorization": "Bearer hidden"}]


def make_review_store(tmp_path: Path) -> tuple[AtelierStore, dict[str, Any], dict[str, Any]]:
    app_dir = tmp_path / "apps" / "sample-app"
    app_dir.mkdir(parents=True)
    (app_dir / "app.yaml").write_text("id: sample-app\n", encoding="utf-8")
    store = AtelierStore(tmp_path / ".atelier" / "atelier.db")
    store.upsert_app(
        app_id="sample-app",
        display_name="Sample App",
        entry_profile="sample-app--entry",
        source_path=str(app_dir),
        definition_revision="rev1",
        definition={"id": "sample-app"},
    )
    run = store.create_run(
        app_id="sample-app",
        scenario_id="smoke",
        root_profile="sample-app--entry",
        definition_revision="rev1",
        input_text="input",
        memory_scope=None,
        user_label=None,
    )
    store.update_run(run["id"], status="completed", output_text="result")
    store.add_event(
        atelier_run_id=run["id"],
        span_id=None,
        profile="sample-app--entry",
        hermes_run_id="run_root",
        event_type="run.completed",
        timestamp=1,
        payload={"event": "run.completed", "Authorization": "Bearer hidden"},
    )
    review = store.create_review(app_id="sample-app", run_ids=[run["id"]])
    return store, run, review


@pytest.mark.asyncio
async def test_freeze_bundle_contains_only_selected_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store, run, review = make_review_store(tmp_path)
    service = ReviewService(
        store,
        profiles=StubProfiles(),  # type: ignore[arg-type]
        client_factory=SessionClient,
    )

    bundle = await service.freeze_bundle(service.required(review["id"]), "human note")

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    event_text = (bundle / "events.jsonl").read_text(encoding="utf-8")
    session = json.loads(next((bundle / "sessions").iterdir()).read_text(encoding="utf-8"))
    assert manifest["run_ids"] == [run["id"]]
    assert "hidden" not in event_text
    assert session[0]["Authorization"] == "[REDACTED]"
    assert (bundle / "app-definition" / "app.yaml").is_file()


def test_reviewer_output_requires_ordered_sections() -> None:
    ReviewService._validate_output("\n".join(REQUIRED_REVIEW_HEADINGS))
    with pytest.raises(AtelierError, match="missing required"):
        ReviewService._validate_output("OBSERVATIONS\nEVIDENCE")
