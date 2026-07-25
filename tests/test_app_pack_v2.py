from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin.atelier.app_pack import AppPack, build_definition_snapshot, release_pack


def create_pack(root: Path) -> Path:
    import yaml

    for agent in ("dispatcher", "product"):
        profile = root / "profiles" / agent
        profile.mkdir(parents=True)
        (profile / "distribution.yaml").write_text(
            f"name: {agent}\nversion: 2.0.0\n", encoding="utf-8"
        )
        (profile / "SOUL.md").write_text(f"# {agent}\n", encoding="utf-8")
    (root / "cases").mkdir()
    (root / "cases" / "smoke.yaml").write_text(
        "id: smoke\ninput: hello\nmemory_policy: clean\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": 2,
        "id": "support",
        "version": "2.0.0",
        "entry": "dispatcher",
        "agents": {
            "dispatcher": {
                "distribution": "profiles/dispatcher",
                "exposure": "public",
            },
            "product": {
                "distribution": "profiles/product",
                "exposure": "internal",
            },
        },
        "allowed_calls": {"dispatcher": ["product"]},
        "collaboration": ["profile_call"],
        "public_api": {
            "protocol": "openai",
            "endpoints": ["/v1/responses", "/v1/chat/completions"],
        },
        "state_policy": "session_only",
        "cases": ["cases/smoke.yaml"],
    }
    (root / "app.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return root


def test_app_pack_uses_logical_agents_and_materializes_instance_mapping(tmp_path: Path) -> None:
    pack = AppPack.load(create_pack(tmp_path / "support"))

    mapping = pack.runtime_mapping(
        instance="customer-a",
        agent_base_urls={
            "dispatcher": "http://127.0.0.1:8080",
            "product": "http://127.0.0.1:8081",
        },
        api_key_env="HERMES_APP_API_KEY",
        current_agent="dispatcher",
    )

    assert pack.entry == "dispatcher"
    assert mapping["agents"]["product"]["profile"] == "customer-a--product"
    assert mapping["agents"]["product"]["base_url"] == "http://127.0.0.1:8081"
    assert "customer-a--product" not in (pack.root / "app.yaml").read_text()


def test_app_pack_rejects_workflow_fields(tmp_path: Path) -> None:
    root = create_pack(tmp_path / "support")
    with (root / "app.yaml").open("a", encoding="utf-8") as output:
        output.write("steps: [route, aggregate]\n")

    with pytest.raises(ValueError, match="workflow key"):
        AppPack.load(root)


def test_definition_snapshot_binds_execution_assets(tmp_path: Path) -> None:
    root = create_pack(tmp_path / "support")
    pack = AppPack.load(root)
    first = build_definition_snapshot(pack)
    (root / "profiles" / "product" / "SOUL.md").write_text("# changed\n", encoding="utf-8")
    second = build_definition_snapshot(AppPack.load(root))

    assert first["revision"] != second["revision"]
    assert first["agents"]["product"]["files"]["SOUL.md"] != second["agents"]["product"][
        "files"
    ]["SOUL.md"]


def test_release_excludes_runtime_state_and_generates_lock(tmp_path: Path) -> None:
    source = create_pack(tmp_path / "support")
    (source / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    (source / "local").mkdir()
    (source / "local" / "app-runtime.json").write_text("{}", encoding="utf-8")
    (source / "sessions").mkdir()
    destination = tmp_path / "release"

    result = release_pack(AppPack.load(source), destination, git_revision="abc123")

    assert not (destination / ".env").exists()
    assert not (destination / "local").exists()
    assert not (destination / "sessions").exists()
    lock = json.loads((destination / "app.lock").read_text(encoding="utf-8"))
    assert lock["pack_revision"] == result["revision"]
    assert lock["git_revision"] == "abc123"
    assert "secret" not in json.dumps(lock)
    assert (destination / "app").stat().st_mode & 0o111
    assert (destination / "profiles" / "dispatcher" / "plugins" / "profile_call").is_dir()
    assert not (destination / "profiles" / "product" / "plugins" / "profile_call").exists()
    assert "profile_call" in (
        destination / "profiles" / "dispatcher" / "config.yaml"
    ).read_text(encoding="utf-8")
