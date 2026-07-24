from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plugin.atelier.errors import AtelierError
from plugin.atelier.services.apps import AppService
from plugin.atelier.services.proposals import ProposalService, validate_patch
from plugin.atelier.store import AtelierStore


class FailFirstInstall:
    def __init__(self) -> None:
        self.install_attempts = 0

    def model_environment(self, profile: str) -> dict[str, str]:
        return {}

    def install_distribution(self, source: Path, profile: str) -> Path:
        self.install_attempts += 1
        if self.install_attempts == 1:
            raise AtelierError("profile_install_failed", "simulated update failure")
        return source

    def configure_runtime(
        self, profile: str, *, app_id: str | None, model_env: dict[str, str]
    ) -> dict[str, str]:
        return {"profile": profile, "status": "stopped"}

    def restart(self, profile: str) -> dict[str, str]:
        return {"profile": profile, "status": "healthy"}

    def stop(self, profile: str) -> dict[str, str]:
        return {"profile": profile, "status": "stopped"}


def test_patch_rejects_other_apps_runtime_and_traversal() -> None:
    invalid = [
        "diff --git a/apps/other/file b/apps/other/file\n",
        "diff --git a/.atelier/atelier.db b/.atelier/atelier.db\n",
        "diff --git a/apps/sample-app/../other b/apps/sample-app/../other\n",
        "diff --git a/apps/sample-app/.env b/apps/sample-app/.env\n",
    ]
    for patch in invalid:
        with pytest.raises(AtelierError):
            validate_patch(patch, "sample-app")


def init_repo(tmp_path: Path) -> tuple[AtelierStore, Path]:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    app = tmp_path / "apps" / "sample-app"
    (app / "profiles" / "entry").mkdir(parents=True)
    (app / "profiles" / "entry" / "distribution.yaml").write_text(
        "name: sample-app--entry\nversion: 1.0.0\n", encoding="utf-8"
    )
    (app / "scenarios").mkdir()
    (app / "scenarios" / "smoke.txt").write_text("before\n", encoding="utf-8")
    (app / "app.yaml").write_text(
        """schema_version: 1
id: sample-app
display_name: Sample App
entry_profile: sample-app--entry
profiles:
  - name: sample-app--entry
    source: profiles/entry
allowed_calls: {}
scenarios_dir: scenarios
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    store = AtelierStore(tmp_path / ".atelier" / "atelier.db")
    AppService(store).register(app)
    return store, app


def test_apply_and_revert_path_validated_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store, app = init_repo(tmp_path)
    patch = """diff --git a/apps/sample-app/scenarios/smoke.txt \
b/apps/sample-app/scenarios/smoke.txt
index 9c59e24..e019be0 100644
--- a/apps/sample-app/scenarios/smoke.txt
+++ b/apps/sample-app/scenarios/smoke.txt
@@ -1 +1 @@
-before
+after
"""
    service = ProposalService(store, apps=AppService(store))
    proposal = service.register_patch(app_id="sample-app", patch=patch)

    applied = service.apply(proposal["id"])
    assert applied["proposal"]["status"] == "applied"
    assert (app / "scenarios" / "smoke.txt").read_text(encoding="utf-8") == "after\n"

    reverted = service.revert(proposal["id"])
    assert reverted["status"] == "reverted"
    assert (app / "scenarios" / "smoke.txt").read_text(encoding="utf-8") == "before\n"


def test_apply_failure_rolls_back_source_registration_and_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store, app = init_repo(tmp_path)
    original_revision = store.get_app("sample-app")["definition_revision"]  # type: ignore[index]
    distribution = app / "profiles" / "entry" / "distribution.yaml"
    patch = (
        "diff --git a/apps/sample-app/profiles/entry/distribution.yaml "
        "b/apps/sample-app/profiles/entry/distribution.yaml\n"
        """--- a/apps/sample-app/profiles/entry/distribution.yaml
+++ b/apps/sample-app/profiles/entry/distribution.yaml
@@ -1,2 +1,2 @@
 name: sample-app--entry
-version: 1.0.0
+version: 2.0.0
"""
    )
    profiles = FailFirstInstall()
    service = ProposalService(
        store,
        apps=AppService(store),
        profiles=profiles,  # type: ignore[arg-type]
    )
    proposal = service.register_patch(app_id="sample-app", patch=patch)

    with pytest.raises(AtelierError, match="affected Profiles rolled back"):
        service.apply(proposal["id"])

    assert distribution.read_text(encoding="utf-8") == (
        "name: sample-app--entry\nversion: 1.0.0\n"
    )
    assert store.get_app("sample-app")["definition_revision"] == original_revision  # type: ignore[index]
    assert service.detail(proposal["id"])["status"] == "patch_apply_failed"
    assert profiles.install_attempts == 2
    assert subprocess.run(
        ["git", "diff", "--quiet"], cwd=tmp_path, check=False
    ).returncode == 0
