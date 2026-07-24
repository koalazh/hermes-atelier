from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from plugin.atelier.paths import project_root
from plugin.atelier.schemas import load_app_definition
from plugin.atelier.services.apps import AppService
from plugin.atelier.store import AtelierStore


class ToolContext:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def register_tool(self, *, name: str, handler: Any, **_: Any) -> None:
        self.tools[name] = handler


def load_plugin(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"example_{path.parent.name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_applications_share_only_the_generic_contract() -> None:
    mini_voc = load_app_definition(project_root() / "apps" / "mini-voc" / "app.yaml")
    defense = load_app_definition(project_root() / "apps" / "project-defense" / "app.yaml")

    assert len(mini_voc.profiles) == 3
    assert len(defense.profiles) == 4
    assert set(mini_voc.allowed_calls) == {"mini-voc--dispatcher"}
    assert set(defense.allowed_calls) == {"project-defense--host"}

    core = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project_root() / "plugin" / "atelier").rglob("*.py")
    )
    assert "mini-voc" not in core
    assert "project-defense" not in core


def test_mini_voc_specialists_expose_distinct_simulated_tools() -> None:
    app = project_root() / "apps" / "mini-voc" / "profiles"
    product = load_plugin(
        app / "product" / "plugins" / "mini-voc-product-tools" / "__init__.py"
    )
    transaction = load_plugin(
        app / "transaction" / "plugins" / "mini-voc-transaction-tools" / "__init__.py"
    )
    context = ToolContext()
    product.register(context)
    transaction.register(context)

    product_result = json.loads(context.tools["voc_product_lookup"]({"query": "登录"}))
    transaction_result = json.loads(
        context.tools["voc_transaction_lookup"]({"order_id": "ORD-1001"})
    )

    assert product_result["matches"][0]["record_id"] == "PRD-LOGIN-17"
    assert transaction_result["record"]["status"] == "refunded"
    with pytest.raises(RuntimeError, match="simulated transaction provider unavailable"):
        context.tools["voc_transaction_lookup"]({"order_id": "ORD-FAIL"})


def test_source_reader_is_constrained_and_source_profile_has_no_write_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(project_root()))
    source = project_root() / "apps" / "project-defense" / "profiles" / "source"
    module = load_plugin(
        source / "plugins" / "project-defense-source-reader" / "__init__.py"
    )
    context = ToolContext()
    module.register(context)

    result = json.loads(
        context.tools["defense_source_read"](
            {"operation": "search", "path": ".", "query": "p99"}
        )
    )
    assert result["matches"][0]["path"] == "README.md"
    with pytest.raises(ValueError, match="escapes"):
        context.tools["defense_source_read"]({"operation": "read", "path": "../app.yaml"})

    config = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    disabled = set(config["agent"]["disabled_toolsets"])
    assert {"terminal", "file", "code_execution"} <= disabled


def test_examples_cover_no_call_multi_call_failure_and_evidence_gap() -> None:
    voc_scenarios = {
        path.stem for path in (project_root() / "apps" / "mini-voc" / "scenarios").glob("*.yaml")
    }
    defense_scenarios = {
        path.stem
        for path in (project_root() / "apps" / "project-defense" / "scenarios").glob("*.yaml")
    }

    assert {"clarify", "cross-domain", "expert-failure"} <= voc_scenarios
    assert {"evidence-gap", "architecture", "coach-only"} <= defense_scenarios


def test_app_detail_exposes_saved_scenarios_and_revision_tracks_profile_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = project_root() / "apps" / "mini-voc"
    app_dir = tmp_path / "apps" / "mini-voc"
    shutil.copytree(source, app_dir)
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    service = AppService(AtelierStore(tmp_path / "atelier.db"))
    first = service.register(app_dir)
    scenarios = service.get("mini-voc")["scenarios"]
    skill = app_dir / "profiles" / "dispatcher" / "skills" / "mini-voc-dispatch" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nrevision marker\n", encoding="utf-8")
    second = service.register(app_dir)

    assert {item["id"] for item in scenarios} >= {"clarify", "product"}
    assert all(item["input"] for item in scenarios)
    assert len(first["definition_revision"]) == 16
    assert second["definition_revision"] != first["definition_revision"]
