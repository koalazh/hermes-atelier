from __future__ import annotations

import json
from typing import Any

import pytest

import plugin.atelier as atelier_plugin


class FakeContext:
    profile_name = "sample-app--entry"

    def __init__(self) -> None:
        self.registration: dict[str, Any] = {}

    def register_tool(self, **kwargs: Any) -> None:
        self.registration = kwargs


@pytest.mark.asyncio
async def test_plugin_handler_receives_hermes_dispatch_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeRunService:
        def __init__(self, _store: Any):
            pass

        async def call(self, args: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append({"args": args, **kwargs})
            return {"ok": True}

    monkeypatch.setattr(atelier_plugin, "RunService", FakeRunService)
    context = FakeContext()
    atelier_plugin.register(context)

    result = await context.registration["handler"](
        {"target": "sample-app--expert", "task": "work"},
        task_id="at_123",
        session_id="at_123",
    )

    assert json.loads(result) == {"ok": True}
    assert calls == [
        {
            "args": {"target": "sample-app--expert", "task": "work"},
            "source_profile": "sample-app--entry",
            "task_id": "at_123",
            "session_id": "at_123",
        }
    ]
    assert context.registration["name"] == "atelier_call"
    assert context.registration["is_async"] is True
