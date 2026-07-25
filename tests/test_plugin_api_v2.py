from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from plugin.atelier import plugin_api_v2
from plugin.atelier.app_pack import AppPack, release_pack
from plugin.atelier.pack_app import PackRuntime
from plugin.atelier.studio_store import StudioStore
from tests.test_app_pack_v2 import create_pack
from tests.test_pack_app_v2 import FakeHermes


def test_trace_visibility_is_honest_about_observation_limits() -> None:
    assert plugin_api_v2._trace_visibility([]) == "unobserved_collaboration_possible"
    assert (
        plugin_api_v2._trace_visibility(
            [
                {
                    "event": "profile_call.started",
                    "call_id": "call-1",
                }
            ]
        )
        == "partial_trace"
    )
    assert (
        plugin_api_v2._trace_visibility(
            [
                {
                    "event": "profile_call.started",
                    "call_id": "call-1",
                },
                {
                    "event": "profile_call.completed",
                    "call_id": "call-1",
                },
            ]
        )
        == "complete_trace"
    )


@pytest.mark.asyncio
async def test_pack_workspace_discovers_instance_and_recent_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_pack(tmp_path / "apps" / "support")
    released = tmp_path / "release"
    release_pack(AppPack.load(source), released)
    home = tmp_path / "hermes"
    runtime = PackRuntime(released, hermes_home=home, hermes_runner=FakeHermes(home))
    runtime.install(instance="demo")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    runtime.configure(
        instance="demo",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )

    observed: dict[str, Any] = {}

    class FakeSessionsClient:
        def __init__(self, base_url: str, api_key: str) -> None:
            observed["base_url"] = base_url
            observed["api_key"] = api_key

        async def sessions(self, *, limit: int) -> list[dict[str, Any]]:
            observed["limit"] = limit
            return [{"id": "recent-session", "title": "Recent"}]

    monkeypatch.setattr(plugin_api_v2, "apps_root", lambda: source.parent)
    monkeypatch.setattr(plugin_api_v2, "atelier_root", lambda: tmp_path / ".atelier")
    monkeypatch.setattr(
        plugin_api_v2,
        "store",
        StudioStore(tmp_path / ".atelier" / "v2"),
    )
    monkeypatch.setattr(plugin_api_v2, "HermesHTTPClient", FakeSessionsClient)
    monkeypatch.setenv("HERMES_HOME", str(home))

    workspace = await plugin_api_v2.pack_workspace("support")

    assert workspace["instances"][0]["instance"] == "demo"
    assert workspace["sessions"] == [{"id": "recent-session", "title": "Recent"}]
    assert workspace["experiments"] == []
    assert workspace["session_discovery"] == {
        "status": "available",
        "instance": "demo",
    }
    assert observed == {
        "base_url": "http://127.0.0.1:9123",
        "api_key": "gateway-secret-value",
        "limit": 20,
    }
    assert "api_key" not in str(workspace)


def test_dashboard_bundle_exposes_app_pack_workspace_without_manual_session_id() -> None:
    bundle = (
        Path(__file__).resolve().parents[1]
        / "plugin"
        / "atelier"
        / "dashboard"
        / "dist"
        / "index_v2.js"
    ).read_text(encoding="utf-8")

    for section in (
        "Overview",
        "Design",
        "Sessions & Evidence",
        "Cases",
        "Delivery",
        "Assurance Lab",
    ):
        assert section in bundle
    assert "Export handoff" in bundle
    assert "Generate with Hermes" in bundle
    assert "Export evidence bundle" in bundle
    assert "Review with Hermes (optional)" in bundle
    assert "Recent entry Session" in bundle
    assert "Validated release" not in bundle
