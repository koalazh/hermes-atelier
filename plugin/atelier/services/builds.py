from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from ..errors import AtelierError
from ..hermes_http import HermesHTTPClient
from ..paths import apps_root, drafts_root, ensure_within, project_root
from ..redaction import redact_text
from ..schemas import BuildRequest, load_app_definition
from ..store import AtelierStore
from .apps import AppService
from .profiles import ProfileService
from .runs import event_type, final_output

BUILD_TEMPLATE = """# Build Contract

## Original Request

{request}

## Aligned Goal

Pending Builder alignment.

## Users and Inputs

Pending.

## Expected Output

Pending.

## Profile Boundaries

Pending.

## Tools and Data

Pending.

## Memory and Skill Ownership

Pending.

## HTTP Collaboration

All cross-Profile calls must use `atelier_call` and the approved `allowed_calls` boundary.

## Observability Needs

Pending.

## Acceptance Scenarios

Pending.

## Missing Real Integrations

Pending.

## Risks

Pending.

## Status

DRAFT
"""


class BuildService:
    def __init__(
        self,
        store: AtelierStore,
        *,
        profiles: ProfileService | None = None,
        apps: AppService | None = None,
        client_factory: Any = HermesHTTPClient,
    ) -> None:
        self.store = store
        self.profiles = profiles or ProfileService(store)
        self.apps = apps or AppService(store)
        self.client_factory = client_factory
        self._tasks: set[asyncio.Task] = set()

    def create(self, request: BuildRequest) -> dict[str, Any]:
        active = {
            "draft",
            "builder_running",
            "awaiting_approval",
            "approving",
        }
        if any(build["status"] in active for build in self.store.list_builds()):
            raise AtelierError(
                "builder_failed",
                "V1 permits one active Build so the Builder has one exact working directory",
            )
        drafts_root().mkdir(parents=True, exist_ok=True)
        placeholder = drafts_root() / "pending"
        build = self.store.create_build(
            original_request=request.request,
            user_label=request.user_label,
            draft_path=str(placeholder),
        )
        draft = drafts_root() / build["id"]
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE builds SET draft_path=? WHERE id=?", (str(draft), build["id"])
            )
        draft.mkdir(parents=True)
        (draft / "BUILD.md").write_text(
            BUILD_TEMPLATE.format(request=redact_text(request.request)), encoding="utf-8"
        )
        build = self.required(build["id"])
        task = asyncio.create_task(self.execute(build["id"]))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return self.detail(build["id"])

    async def execute(self, build_id: str) -> dict[str, Any]:
        build = self.required(build_id)
        draft = ensure_within(Path(build["draft_path"]), drafts_root())
        try:
            self.profiles.restart("atelier-builder", terminal_cwd=draft)
            base_url, key = self.profiles.endpoint_credentials("atelier-builder")
            client = self.client_factory(base_url, key)
            prompt = (
                f"Work only in {draft}. Read and maintain BUILD.md. Align the business goal "
                "dynamically, then create one complete application beneath this directory. "
                "Do not write to formal apps/. Stop after setting BUILD.md Status to "
                "AWAITING_APPROVAL and summarize the proposed Profiles and acceptance "
                "scenarios.\n\n"
                f"Original request:\n{build['original_request']}"
            )
            self.store.update_build(build_id, status="builder_running")
            run_id = await client.start_run(
                task=prompt,
                session_id=build["builder_session_id"],
                instructions=(
                    "You are atelier-builder. The backend, not natural language, owns approval. "
                    "Never claim that a formal application was approved or installed."
                ),
            )
            self.store.update_build(build_id, builder_hermes_run_id=run_id)
            output_parts: list[str] = []
            terminal: dict[str, Any] | None = None
            async for event in client.events(run_id):
                if event_type(event) == "message.delta" and isinstance(event.get("delta"), str):
                    output_parts.append(event["delta"])
                if event_type(event).startswith("run."):
                    terminal = event
            if terminal is None:
                terminal = await client.status(run_id)
            status = str(terminal.get("status") or event_type(terminal).removeprefix("run."))
            output = "".join(output_parts) or final_output(terminal)
            if status != "completed" and event_type(terminal) != "run.completed":
                raise AtelierError("builder_failed", str(terminal.get("error") or status))
            self._validate_draft(draft)
            self.store.update_build(
                build_id, status="awaiting_approval", builder_output=redact_text(output)
            )
        except Exception as exc:
            self.store.update_build(
                build_id, status="builder_failed", last_error=redact_text(str(exc))[:2000]
            )
        return self.detail(build_id)

    def approve(self, build_id: str) -> dict[str, Any]:
        build = self.required(build_id)
        if build["status"] != "awaiting_approval":
            raise AtelierError("builder_failed", "Build is not awaiting explicit approval")
        draft = ensure_within(Path(build["draft_path"]), drafts_root())
        app_dir, definition = self._validate_draft(draft)
        destination = apps_root() / definition.id
        if destination.exists():
            raise AtelierError(
                "builder_failed", f"formal application already exists: {definition.id}"
            )
        self.store.update_build(build_id, status="approving")
        try:
            shutil.copytree(app_dir, destination)
            app = self.apps.register(destination)
            model_env = self.profiles.model_environment("atelier-builder")
            self.profiles.install_app(destination, definition, model_env=model_env)
            for profile in definition.profiles:
                self.profiles.start(profile.name)
            self.store.update_build(build_id, status="approved", app_id=definition.id)
            return {"build": self.detail(build_id), "app": app}
        except Exception as exc:
            if destination.exists():
                failed = project_root() / ".atelier" / "failed-builds" / build_id
                failed.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(failed)
            self.store.delete_app(definition.id)
            self.store.update_build(
                build_id,
                status="profile_install_failed",
                last_error=redact_text(str(exc))[:2000],
            )
            raise AtelierError("profile_install_failed", str(exc)) from exc

    def detail(self, build_id: str) -> dict[str, Any]:
        build = self.required(build_id)
        value = dict(build)
        contract = Path(build["draft_path"]) / "BUILD.md"
        value["build_contract"] = contract.read_text(encoding="utf-8") if contract.is_file() else ""
        return value

    def required(self, build_id: str) -> dict[str, Any]:
        build = self.store.get_build(build_id)
        if build is None:
            raise KeyError(f"unknown Build: {build_id}")
        return build

    @staticmethod
    def _validate_draft(draft: Path) -> tuple[Path, Any]:
        candidates = []
        for path in draft.rglob("*"):
            if path.is_symlink():
                raise AtelierError("builder_failed", f"draft symlinks are forbidden: {path}")
            if path.name in {".env", "auth.json"}:
                raise AtelierError("builder_failed", f"draft contains runtime secret file: {path}")
            if path.name == "app.yaml":
                candidates.append(path.parent)
        if len(candidates) != 1:
            raise AtelierError("builder_failed", "draft must contain exactly one application")
        definition = load_app_definition(candidates[0] / "app.yaml")
        return candidates[0], definition
