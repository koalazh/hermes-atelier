from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from plugin.atelier.dashboard import plugin_api
from plugin.atelier.services.apps import AppService
from plugin.atelier.store import AtelierStore


@pytest.mark.asyncio
async def test_dashboard_apps_feedback_and_loopback_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AtelierStore(tmp_path / "atelier.db")
    store.upsert_app(
        app_id="sample-app",
        display_name="Sample App",
        entry_profile="sample-app--entry",
        source_path=str(tmp_path / "sample-app"),
        definition_revision="rev",
        definition={"id": "sample-app"},
    )
    run = store.create_run(
        app_id="sample-app",
        scenario_id=None,
        root_profile="sample-app--entry",
        definition_revision="rev",
        input_text="test",
        memory_scope=None,
        user_label=None,
    )
    monkeypatch.setattr(plugin_api, "store", store)
    monkeypatch.setattr(plugin_api, "apps", AppService(store))
    app = FastAPI()
    app.include_router(plugin_api.router, prefix="/api/plugins/atelier")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        apps = await client.get("/api/plugins/atelier/apps")
        feedback = await client.post(
            f"/api/plugins/atelier/runs/{run['id']}/feedback",
            json={"outcome": "partial", "feedback": "needs evidence"},
        )
        monkeypatch.setenv("HERMES_DASHBOARD_HOST", "0.0.0.0")
        rejected = await client.get("/api/plugins/atelier/apps")

    assert apps.status_code == 200
    assert apps.json()["items"][0]["id"] == "sample-app"
    assert feedback.json()["outcome"] == "partial"
    assert rejected.status_code == 403


def test_dashboard_manifest_uses_sdk_bundle() -> None:
    root = Path(plugin_api.__file__).resolve().parent
    source = (root / "dist" / "index.js").read_text(encoding="utf-8")
    assert "window.__HERMES_PLUGIN_SDK__" in source
    assert "window.__HERMES_PLUGINS__" in source
    assert 'from "react"' not in source
