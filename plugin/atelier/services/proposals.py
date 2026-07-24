from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from ..errors import AtelierError
from ..hermes_http import HermesHTTPClient
from ..paths import apps_root, atelier_root, drafts_root, ensure_within, project_root
from ..redaction import redact_text
from ..schemas import AppDefinition
from ..store import AtelierStore, now_iso
from .apps import AppService
from .profiles import ProfileService
from .reviews import ReviewService
from .runs import event_type

DIFF_PATH_RE = re.compile(r"^(?:---|\+\+\+)\s+([^\t ]+)|^diff --git\s+(\S+)\s+(\S+)$")


def patch_paths(patch: str) -> set[str]:
    paths: set[str] = set()
    for line in patch.splitlines():
        match = DIFF_PATH_RE.match(line)
        if not match:
            continue
        for raw in match.groups():
            if raw and raw != "/dev/null":
                paths.add(raw[2:] if raw.startswith(("a/", "b/")) else raw)
    return paths


def validate_patch(patch: str, app_id: str) -> set[str]:
    if not patch.strip():
        raise AtelierError("proposal_invalid", "proposal patch is empty")
    paths = patch_paths(patch)
    if not paths:
        raise AtelierError("proposal_invalid", "proposal contains no file paths")
    prefix = PurePosixPath("apps") / app_id
    forbidden_names = {".env", "auth.json", "atelier.db"}
    for value in paths:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise AtelierError("proposal_invalid", f"unsafe patch path: {value}")
        try:
            relative = path.relative_to(prefix)
        except ValueError as exc:
            raise AtelierError(
                "proposal_invalid", f"patch path is outside apps/{app_id}: {value}"
            ) from exc
        if not relative.parts or any(part in forbidden_names for part in relative.parts):
            raise AtelierError("proposal_invalid", f"forbidden patch path: {value}")
    return paths


class ProposalService:
    def __init__(
        self,
        store: AtelierStore,
        *,
        profiles: ProfileService | None = None,
        apps: AppService | None = None,
        reviews: ReviewService | None = None,
        client_factory: Any = HermesHTTPClient,
    ) -> None:
        self.store = store
        self.profiles = profiles or ProfileService(store)
        self.apps = apps or AppService(store)
        self.reviews = reviews or ReviewService(store, profiles=self.profiles)
        self.client_factory = client_factory
        self._tasks: set[asyncio.Task] = set()

    def request(self, review_id: str) -> dict[str, Any]:
        review = self.reviews.required(review_id)
        if review["status"] != "completed":
            raise AtelierError("proposal_invalid", "Review must be complete")
        proposal_id = uuid.uuid4().hex
        final_path = atelier_root() / "proposals" / f"{proposal_id}.patch"
        proposal = self.store.create_proposal(
            app_id=review["app_id"],
            review_id=review_id,
            patch_path=str(final_path),
            proposal_id=proposal_id,
            status="generating",
        )
        task = asyncio.create_task(self.generate(proposal_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return proposal

    async def generate(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.required(proposal_id)
        review = self.reviews.detail(proposal["review_id"])
        app = self.store.get_app(proposal["app_id"])
        if app is None:
            raise AtelierError("proposal_invalid", "application no longer exists")
        draft = drafts_root() / f"proposal-{proposal_id}"
        draft.mkdir(parents=True)
        shutil.copytree(Path(app["source_path"]), draft / "current-app")
        (draft / "REVIEW.md").write_text(review["result"], encoding="utf-8")
        try:
            self.profiles.restart("atelier-builder", terminal_cwd=draft)
            base_url, key = self.profiles.endpoint_credentials("atelier-builder")
            client = self.client_factory(base_url, key)
            run_id = await client.start_run(
                task=(
                    f"Read REVIEW.md and current-app for app {proposal['app_id']}. Create only "
                    f"candidate.patch in {draft}. The patch paths must be rooted at "
                    f"apps/{proposal['app_id']}/. Do not modify the formal repository. "
                    "Include only changes supported by Review evidence; do not change evaluation "
                    "scenarios to claim improvement."
                ),
                session_id=f"atelier_proposal_{proposal_id}",
            )
            terminal = None
            async for event in client.events(run_id):
                if event_type(event).startswith("run."):
                    terminal = event
            if terminal is None:
                terminal = await client.status(run_id)
            status = str(terminal.get("status") or event_type(terminal).removeprefix("run."))
            if status != "completed" and event_type(terminal) != "run.completed":
                raise AtelierError("proposal_invalid", str(terminal.get("error") or status))
            candidate = draft / "candidate.patch"
            if not candidate.is_file():
                raise AtelierError("proposal_invalid", "Builder did not create candidate.patch")
            patch = candidate.read_text(encoding="utf-8")
            validate_patch(patch, proposal["app_id"])
            final_path = Path(proposal["patch_path"])
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_text(patch, encoding="utf-8")
            self._dry_run(final_path)
            self.store.update_proposal(proposal_id, status="pending")
            self.store.update_review(review["id"], proposal_path=str(final_path))
        except Exception as exc:
            self.store.update_proposal(
                proposal_id, status="proposal_invalid", apply_result=redact_text(str(exc))[:2000]
            )
        return self.detail(proposal_id)

    def register_patch(
        self, *, app_id: str, patch: str, review_id: str | None = None
    ) -> dict[str, Any]:
        if self.store.get_app(app_id) is None:
            raise KeyError(f"unknown application: {app_id}")
        validate_patch(patch, app_id)
        proposal_id = uuid.uuid4().hex
        path = atelier_root() / "proposals" / f"{proposal_id}.patch"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(patch, encoding="utf-8")
        self._dry_run(path)
        return self.store.create_proposal(
            app_id=app_id,
            review_id=review_id,
            patch_path=str(path),
            proposal_id=proposal_id,
        )

    def apply(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.required(proposal_id)
        if proposal["status"] != "pending":
            raise AtelierError("proposal_invalid", "proposal is not pending approval")
        patch_file = ensure_within(Path(proposal["patch_path"]), atelier_root() / "proposals")
        patch = patch_file.read_text(encoding="utf-8")
        paths = validate_patch(patch, proposal["app_id"])
        self._dry_run(patch_file)
        original_definition = self.apps.get_definition(proposal["app_id"])
        original_affected = self._affected_profiles(original_definition, paths)
        original_running = {
            profile.name: bool(
                (endpoint := self.store.get_endpoint(profile.name))
                and endpoint["status"] in {"healthy", "starting"}
            )
            for profile in original_affected
        }
        endpoints_before = {item["profile"] for item in self.store.list_endpoints()}
        self.store.update_proposal(proposal_id, status="approved", approved_at=now_iso())
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_file)],
            cwd=project_root(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.store.update_proposal(
                proposal_id,
                status="patch_apply_failed",
                apply_result=redact_text(result.stderr or result.stdout)[:2000],
            )
            raise AtelierError("patch_apply_failed", result.stderr or result.stdout)
        try:
            app = self.apps.register(apps_root() / proposal["app_id"])
            definition = self.apps.get_definition(proposal["app_id"])
            affected = self._affected_profiles(definition, paths)
            model_env = self.profiles.model_environment("atelier-builder")
            for profile in affected:
                endpoint = self.store.get_endpoint(profile.name)
                was_running = endpoint and endpoint["status"] in {"healthy", "starting"}
                self.profiles.install_distribution(
                    apps_root() / proposal["app_id"] / profile.source, profile.name
                )
                self.profiles.configure_runtime(
                    profile.name, app_id=proposal["app_id"], model_env=model_env
                )
                if was_running:
                    self.profiles.restart(profile.name)
            self.store.update_proposal(
                proposal_id,
                status="applied",
                applied_at=now_iso(),
                apply_result=f"updated profiles: {', '.join(p.name for p in affected) or 'none'}",
            )
            return {"proposal": self.detail(proposal_id), "app": app}
        except Exception as exc:
            rollback_errors: list[str] = []
            reverse = subprocess.run(
                ["git", "apply", "-R", "--whitespace=nowarn", str(patch_file)],
                cwd=project_root(),
                capture_output=True,
                text=True,
            )
            if reverse.returncode != 0:
                rollback_errors.append(reverse.stderr or reverse.stdout or "reverse patch failed")
            else:
                try:
                    self.apps.register(apps_root() / proposal["app_id"])
                    model_env = self.profiles.model_environment("atelier-builder")
                    for profile in original_affected:
                        self.profiles.install_distribution(
                            apps_root() / proposal["app_id"] / profile.source, profile.name
                        )
                        self.profiles.configure_runtime(
                            profile.name, app_id=proposal["app_id"], model_env=model_env
                        )
                        if original_running[profile.name]:
                            self.profiles.restart(profile.name)
                    for endpoint in self.store.list_endpoints():
                        if (
                            endpoint["app_id"] == proposal["app_id"]
                            and endpoint["profile"] not in endpoints_before
                        ):
                            self.profiles.stop(endpoint["profile"])
                            self.store.delete_endpoint(endpoint["profile"])
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            message = str(exc)
            if rollback_errors:
                message = f"{message}; rollback incomplete: {'; '.join(rollback_errors)}"
            else:
                message = f"{message}; source and affected Profiles rolled back"
            self.store.update_proposal(
                proposal_id,
                status="patch_apply_failed",
                apply_result=redact_text(message)[:2000],
            )
            raise AtelierError("patch_apply_failed", message) from exc

    def reject(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.required(proposal_id)
        if proposal["status"] not in {"pending", "generating"}:
            raise AtelierError("proposal_invalid", "only pending proposals can be rejected")
        self.store.update_proposal(proposal_id, status="rejected")
        return self.detail(proposal_id)

    def revert(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.required(proposal_id)
        if proposal["status"] != "applied":
            raise AtelierError("proposal_invalid", "only applied proposals can be reverted")
        patch_file = ensure_within(Path(proposal["patch_path"]), atelier_root() / "proposals")
        result = subprocess.run(
            ["git", "apply", "-R", "--check", str(patch_file)],
            cwd=project_root(),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            result = subprocess.run(
                ["git", "apply", "-R", str(patch_file)],
                cwd=project_root(),
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            raise AtelierError("patch_apply_failed", result.stderr or result.stdout)
        self.apps.register(apps_root() / proposal["app_id"])
        self.store.update_proposal(proposal_id, status="reverted", apply_result="reverted")
        return self.detail(proposal_id)

    def detail(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.required(proposal_id)
        value = dict(proposal)
        path = Path(proposal["patch_path"])
        value["patch"] = path.read_text(encoding="utf-8") if path.is_file() else None
        return value

    def required(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.store.get_proposal(proposal_id)
        if proposal is None:
            raise KeyError(f"unknown Proposal: {proposal_id}")
        return proposal

    @staticmethod
    def _dry_run(patch_file: Path) -> None:
        result = subprocess.run(
            ["git", "apply", "--check", "--whitespace=nowarn", str(patch_file)],
            cwd=project_root(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AtelierError("proposal_invalid", result.stderr or result.stdout)

    @staticmethod
    def _affected_profiles(definition: AppDefinition, paths: set[str]):
        if f"apps/{definition.id}/app.yaml" in paths:
            return list(definition.profiles)
        affected = []
        for profile in definition.profiles:
            prefix = f"apps/{definition.id}/{profile.source.rstrip('/')}/"
            if any(path.startswith(prefix) for path in paths):
                affected.append(profile)
        return affected
