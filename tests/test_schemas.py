from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from plugin.atelier.schemas import AppDefinition, load_app_definition


def valid_definition() -> dict:
    return {
        "schema_version": 1,
        "id": "sample-app",
        "display_name": "Sample App",
        "entry_profile": "sample-app--entry",
        "profiles": [
            {"name": "sample-app--entry", "source": "profiles/entry"},
            {"name": "sample-app--expert", "source": "profiles/expert"},
        ],
        "allowed_calls": {"sample-app--entry": ["sample-app--expert"]},
        "scenarios_dir": "scenarios",
    }


def make_app(tmp_path: Path, definition: dict | None = None) -> Path:
    app_dir = tmp_path / "sample-app"
    for name in ("entry", "expert"):
        profile = app_dir / "profiles" / name
        profile.mkdir(parents=True)
        (profile / "distribution.yaml").write_text(
            f"name: sample-app--{name}\nversion: 1.0.0\n", encoding="utf-8"
        )
    (app_dir / "scenarios").mkdir()
    (app_dir / "app.yaml").write_text(
        yaml.safe_dump(definition or valid_definition(), sort_keys=False), encoding="utf-8"
    )
    return app_dir


def test_load_valid_app_definition(tmp_path: Path) -> None:
    app_dir = make_app(tmp_path)

    definition = load_app_definition(app_dir / "app.yaml")

    assert definition.id == "sample-app"
    assert definition.allows("sample-app--entry", "sample-app--expert")
    assert not definition.allows("sample-app--expert", "sample-app--entry")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("entry_profile", "other--entry", "declared profile"),
        ("allowed_calls", {"sample-app--entry": ["other--expert"]}, "target"),
        ("allowed_calls", {"other--entry": ["sample-app--expert"]}, "source"),
    ],
)
def test_rejects_invalid_profile_membership(field: str, value: object, message: str) -> None:
    raw = valid_definition()
    raw[field] = value
    with pytest.raises(ValueError, match=message):
        AppDefinition.model_validate(raw)


def test_rejects_profile_outside_app_namespace() -> None:
    raw = valid_definition()
    raw["profiles"][1]["name"] = "shared-expert"
    with pytest.raises(ValueError, match="must start"):
        AppDefinition.model_validate(raw)


@pytest.mark.parametrize(
    "key",
    [
        "steps",
        "workflow",
        "if",
        "else",
        "route_when",
        "parallel",
        "fan_out",
        "aggregate",
        "judge",
        "retry_policy_for_business",
    ],
)
def test_rejects_workflow_keys_anywhere(tmp_path: Path, key: str) -> None:
    raw = valid_definition()
    raw["description"] = {"nested": {key: "forbidden"}}
    app_dir = make_app(tmp_path, raw)

    with pytest.raises(ValueError, match="workflow key is forbidden"):
        load_app_definition(app_dir / "app.yaml")


def test_rejects_missing_distribution(tmp_path: Path) -> None:
    app_dir = make_app(tmp_path)
    (app_dir / "profiles" / "expert" / "distribution.yaml").unlink()

    with pytest.raises(ValueError, match="not a Hermes Distribution"):
        load_app_definition(app_dir / "app.yaml")


def test_rejects_path_escape() -> None:
    raw = valid_definition()
    raw["profiles"][0]["source"] = "../entry"
    with pytest.raises(ValueError, match="relative path"):
        AppDefinition.model_validate(raw)
