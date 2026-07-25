from __future__ import annotations

from typing import Any

import plugin.atelier as atelier_plugin


class FakeContext:
    profile_name = "sample-app--entry"

    def __init__(self) -> None:
        self.registration: dict[str, Any] = {}
        self.cli_registration: dict[str, Any] = {}

    def register_tool(self, **kwargs: Any) -> None:
        self.registration = kwargs

    def register_cli_command(self, **kwargs: Any) -> None:
        self.cli_registration = kwargs


def test_studio_plugin_registers_cli_without_application_runtime_tool() -> None:
    context = FakeContext()
    atelier_plugin.register(context)

    assert context.registration == {}
    assert context.cli_registration["name"] == "atelier"
    assert "runtime" in context.cli_registration["description"]
