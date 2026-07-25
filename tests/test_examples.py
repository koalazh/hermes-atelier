from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from plugin.atelier.app_pack import AppPack, build_definition_snapshot
from plugin.atelier.paths import project_root


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
    mini_voc = AppPack.load(project_root() / "apps" / "mini-voc")
    defense = AppPack.load(project_root() / "apps" / "project-defense")

    assert len(mini_voc.manifest.agents) == 3
    assert len(defense.manifest.agents) == 4
    assert set(mini_voc.manifest.allowed_calls) == {"dispatcher"}
    assert set(defense.manifest.allowed_calls) == {"host"}

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


def test_source_reader_is_constrained_and_source_profile_has_no_write_tools() -> None:
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
    voc_cases = {
        path.stem for path in (project_root() / "apps" / "mini-voc" / "cases").glob("*.yaml")
    }
    defense_cases = {
        path.stem
        for path in (project_root() / "apps" / "project-defense" / "cases").glob("*.yaml")
    }

    assert {"clarify", "cross-domain", "expert-failure"} <= voc_cases
    assert {"evidence-gap", "architecture", "coach-only"} <= defense_cases


def test_project_defense_stable_memory_is_scoped_to_coaching() -> None:
    cases = project_root() / "apps" / "project-defense" / "cases"
    coach = yaml.safe_load((cases / "coach-only.yaml").read_text(encoding="utf-8"))
    evidence = yaml.safe_load((cases / "evidence-gap.yaml").read_text(encoding="utf-8"))
    architecture = yaml.safe_load((cases / "architecture.yaml").read_text(encoding="utf-8"))

    assert coach["memory_scope"] == "demo-candidate-durable-queue"
    assert coach["memory_policy"] == "retained"
    assert evidence["memory_policy"] == "clean"
    assert architecture["memory_policy"] == "session_only"


def test_project_defense_architecture_forbids_unmeasured_numbers() -> None:
    profile = project_root() / "apps" / "project-defense" / "profiles" / "architecture"
    soul = (profile / "SOUL.md").read_text(encoding="utf-8")
    skill = (
        profile / "skills" / "project-defense-architecture" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "Never introduce numerical latency" in soul
    assert "do not supply numerical performance estimates" in skill


def test_example_definition_snapshot_tracks_profile_assets() -> None:
    pack = AppPack.load(project_root() / "apps" / "mini-voc")
    snapshot = build_definition_snapshot(pack)

    assert len(snapshot["revision"]) == 64
    assert "SOUL.md" in snapshot["agents"]["dispatcher"]["files"]
