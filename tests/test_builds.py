from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from plugin.atelier.errors import AtelierError
from plugin.atelier.services.apps import AppService
from plugin.atelier.services.builds import BuildService
from plugin.atelier.store import AtelierStore


class FakeProfiles:
    def __init__(self) -> None:
        self.installed: list[str] = []
        self.started: list[str] = []

    def model_environment(self, profile: str) -> dict[str, str]:
        return {}

    def install_app(self, app_dir: Path, definition: Any, *, model_env: dict[str, str]):
        self.installed.append(definition.id)

    def start(self, profile: str):
        self.started.append(profile)
        return {"profile": profile, "status": "healthy"}


def make_draft(root: Path, build_id: str) -> Path:
    draft = root / "apps" / ".drafts" / build_id
    app = draft / "sample-app"
    profile = app / "profiles" / "entry"
    profile.mkdir(parents=True)
    (profile / "distribution.yaml").write_text(
        "name: sample-app--entry\nversion: 1.0.0\n", encoding="utf-8"
    )
    (app / "scenarios").mkdir()
    (app / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "id": "sample-app",
                "display_name": "Sample App",
                "entry_profile": "sample-app--entry",
                "profiles": [{"name": "sample-app--entry", "source": "profiles/entry"}],
                "allowed_calls": {},
                "scenarios_dir": "scenarios",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (draft / "BUILD.md").write_text("# Build\n\nAWAITING_APPROVAL\n", encoding="utf-8")
    return draft


def test_approval_requires_database_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store = AtelierStore(tmp_path / ".atelier" / "atelier.db")
    build = store.create_build(
        original_request="build it",
        user_label=None,
        draft_path=str(tmp_path / "apps" / ".drafts" / "draft"),
    )
    service = BuildService(store, profiles=FakeProfiles())  # type: ignore[arg-type]

    with pytest.raises(AtelierError, match="not awaiting explicit approval"):
        service.approve(build["id"])


def test_explicit_approval_promotes_and_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store = AtelierStore(tmp_path / ".atelier" / "atelier.db")
    build = store.create_build(
        original_request="build it",
        user_label=None,
        draft_path="pending",
    )
    draft = make_draft(tmp_path, build["id"])
    with store.transaction() as connection:
        connection.execute(
            "UPDATE builds SET draft_path=?, status='awaiting_approval' WHERE id=?",
            (str(draft), build["id"]),
        )
    profiles = FakeProfiles()
    service = BuildService(
        store,
        profiles=profiles,  # type: ignore[arg-type]
        apps=AppService(store),
    )

    result = service.approve(build["id"])

    assert result["build"]["status"] == "approved"
    assert (tmp_path / "apps" / "sample-app" / "app.yaml").is_file()
    assert profiles.installed == ["sample-app"]
    assert profiles.started == ["sample-app--entry"]


def test_draft_rejects_symlinks_and_secret_files(tmp_path: Path) -> None:
    draft = make_draft(tmp_path, "draft")
    (draft / "sample-app" / ".env").write_text("SECRET=value\n", encoding="utf-8")

    with pytest.raises(AtelierError, match="runtime secret"):
        BuildService._validate_draft(draft)
