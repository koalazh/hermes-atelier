from __future__ import annotations

from pathlib import Path
from typing import Any

from .app_pack import AppPack
from .hermes_http import HermesHTTPClient
from .redaction import redact_text
from .studio_store import StudioStore

PLAN_TEMPLATE = """# Design Plan

## Original requirement

{requirement}

## Builder alignment

The Builder has not responded yet.
"""

HANDOFF_FALLBACK = """# Implementation Handoff

## Original requirement

{requirement}

## Aligned goal and design context

{plan}

## Why one or multiple Profiles

Use the Profile boundaries and reasons recorded in `PLAN.md`. A single Profile remains the
default when no permission, data, workspace, state, failure, reuse, or context boundary requires
separation.

## Tools, data, and permissions

Use only the tools, data sources, and permission boundaries recorded in `PLAN.md`. Missing real
systems remain unconnected until the implementer supplies them.

## Session, Memory, and Skill ownership

Preserve the ownership decisions in `PLAN.md`; Hermes owns runtime Session and Memory behavior.

## Recommended collaboration primitive

Use the primitive selected in `PLAN.md`. It is a recommendation, not a fixed implementation
workflow, and must not be added to the App Pack schema.

## App Pack and HTTP delivery boundary

Deliver a schema-version 2 App Pack that runs through native Hermes and exposes the declared
OpenAI-compatible entry HTTP endpoint without depending on Atelier or `.atelier`.

## Acceptance Cases

Implement and validate the Cases recorded in `PLAN.md`. Prefer output, evidence, authorization,
unknown, and honest-degradation assertions over fixed call-tree assertions.

## Real systems not connected

Treat every integration identified as missing in `PLAN.md` as missing; do not fabricate access,
credentials, production data, or completed integration work.

## Explicit non-goals

Do not turn Atelier into an application runtime, workflow engine, deployment platform, model
manager, or business router.
"""

PLANNING_INSTRUCTIONS = """You are the Hermes Atelier Builder in the planning stage.
Continue the existing native Hermes Session. Investigate and align the goal; ask focused
questions when missing information materially changes the application. Do not create or edit
an application Draft in this stage. Start every response with exactly
`DESIGN_STATUS: NEEDS_INPUT` or `DESIGN_STATUS: PLAN_READY`. Use NEEDS_INPUT while material
questions remain. Use PLAN_READY only when the remainder is a complete current PLAN.md recording
the aligned goal, users and inputs, expected outcome, justified Profile boundaries, tools/data,
Memory and Session ownership, collaboration primitive, public HTTP contract, Cases, missing
integrations, and risks. The plan is a decision anchor, never a workflow step list.

When ready, return both documents using exactly these separators:
`=== PLAN.md ===` and `=== IMPLEMENTATION_HANDOFF.md ===`.
The handoff targets the developer's chosen Coding Agent or human implementer and covers the
original requirement, aligned goal, why multiple Profiles are or are not needed, Profile
boundaries, tools/data/permissions, Session/Memory/Skill ownership, recommended collaboration
primitive, App Pack and HTTP delivery boundaries, acceptance Cases, unconnected real systems,
and explicit non-goals. It is an implementation contract, not a fixed workflow.
"""


class DesignService:
    def __init__(
        self,
        store: StudioStore,
        *,
        builder_base_url: str,
        builder_api_key: str,
        drafter_base_url: str | None = None,
        drafter_api_key: str | None = None,
        client_factory: Any = HermesHTTPClient,
    ) -> None:
        self.store = store
        self.builder_base_url = builder_base_url
        self.builder_api_key = builder_api_key
        self.drafter_base_url = drafter_base_url
        self.drafter_api_key = drafter_api_key
        self.client_factory = client_factory

    def create(self, requirement: str) -> dict[str, Any]:
        design = self.store.create_design(requirement=redact_text(requirement))
        Path(design["plan_path"]).write_text(
            PLAN_TEMPLATE.format(requirement=redact_text(requirement)), encoding="utf-8"
        )
        return self.detail(design["id"])

    async def message(self, design_id: str, content: str) -> dict[str, Any]:
        design = self.store.get_design(design_id)
        if design["status"] not in {"conversation", "plan_ready"}:
            raise ValueError("Design is not accepting planning messages")
        task = content
        if not design["messages"]:
            task = (
                f"Original requirement:\n{design['requirement']}\n\nDeveloper message:\n{content}"
            )
        client = self.client_factory(self.builder_base_url, self.builder_api_key)
        await client.ensure_session(
            design["builder_session_id"], title=f"Atelier Design {design_id[:8]}"
        )
        response = await client.chat_session(
            design["builder_session_id"],
            message=task,
            instructions=PLANNING_INSTRUCTIONS,
        )
        output = response["message"]["content"]
        turn_index = len(design["builder_turns"]) + 1
        messages = [
            *design["messages"],
            {"role": "user", "content": redact_text(content)},
            {
                "role": "assistant",
                "content": redact_text(output),
                "hermes_session_id": design["builder_session_id"],
                "turn": turn_index,
            },
        ]
        lines = output.splitlines()
        marker_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.strip() in {"DESIGN_STATUS: NEEDS_INPUT", "DESIGN_STATUS: PLAN_READY"}
            ),
            None,
        )
        if marker_index is None:
            raise ValueError("Builder response omitted DESIGN_STATUS")
        ready = lines[marker_index].strip() == "DESIGN_STATUS: PLAN_READY"
        if ready:
            ready_output = "\n".join(lines[marker_index + 1 :])
            plan, handoff = self._ready_documents(design, ready_output)
            if not plan.strip():
                raise ValueError("Builder marked PLAN_READY without a plan")
            Path(design["plan_path"]).write_text(
                redact_text(plan).rstrip() + "\n", encoding="utf-8"
            )
            Path(design["handoff_path"]).write_text(
                redact_text(handoff).rstrip() + "\n", encoding="utf-8"
            )
        design.update(
            status="plan_ready" if ready else "conversation",
            messages=messages,
            builder_turns=[
                *design["builder_turns"],
                {
                    "turn": turn_index,
                    "session_id": design["builder_session_id"],
                },
            ],
        )
        self.store.save_design(design)
        return self.detail(design_id)

    async def generate_draft(self, design_id: str) -> dict[str, Any]:
        design = self.store.get_design(design_id)
        if design["status"] != "plan_ready" or not design["messages"]:
            raise ValueError("Generate with Hermes requires an aligned Builder conversation")
        if not self.drafter_base_url or not self.drafter_api_key:
            raise ValueError(
                "Generate with Hermes requires an explicitly configured Drafter Profile"
            )
        draft = Path(design["draft_path"])
        draft.mkdir(parents=True, exist_ok=False)
        design["status"] = "generating_draft"
        self.store.save_design(design)
        prompt = (
            "The developer explicitly selected Generate with Hermes. Read the approved PLAN.md at "
            f"{design['plan_path']} and implementation handoff at {design['handoff_path']}. "
            f"You may now write only beneath {draft}. Generate exactly one "
            "Hermes App Pack V2 Draft. Do not install, start, adopt, commit, or claim approval."
        )
        try:
            output, run_id = await self._run(
                prompt,
                session_id=f"atelier_draft_{design_id}",
                instructions=(
                    "This is the explicit Draft stage. Keep all writes inside the supplied Draft "
                    "directory and stop after generating inspectable files."
                ),
                base_url=self.drafter_base_url,
                api_key=self.drafter_api_key,
            )
            pack_roots = [path.parent for path in draft.rglob("app.yaml")]
            if len(pack_roots) != 1:
                raise ValueError("Builder Draft must contain exactly one app.yaml")
            AppPack.load(pack_roots[0])
            design.update(
                status="draft_ready",
                draft_pack_path=str(pack_roots[0]),
                draft_summary=redact_text(output),
                drafter_run_ids=[*design["drafter_run_ids"], run_id],
            )
        except Exception as exc:
            design.update(status="draft_failed", last_error=redact_text(str(exc))[:2000])
            self.store.save_design(design)
            raise
        self.store.save_design(design)
        return self.detail(design_id)

    def record_candidate(
        self, design_id: str, *, branch: str, worktree: str, diff_summary: str
    ) -> dict[str, Any]:
        design = self.store.get_design(design_id)
        if design["status"] != "draft_ready":
            raise ValueError("Candidate metadata requires an inspectable Draft")
        design.update(
            status="candidate_ready",
            candidate={
                "branch": branch,
                "worktree": worktree,
                "diff_summary": redact_text(diff_summary),
            },
        )
        self.store.save_design(design)
        return self.detail(design_id)

    def detail(self, design_id: str) -> dict[str, Any]:
        design = self.store.get_design(design_id)
        plan = Path(design["plan_path"])
        value = dict(design)
        value["plan"] = plan.read_text(encoding="utf-8") if plan.is_file() else ""
        handoff = Path(str(design.get("handoff_path") or ""))
        value["implementation_handoff"] = (
            handoff.read_text(encoding="utf-8") if handoff.is_file() else ""
        )
        draft_path = Path(str(design.get("draft_pack_path") or design["draft_path"]))
        value["draft_files"] = (
            sorted(
                path.relative_to(draft_path).as_posix()
                for path in draft_path.rglob("*")
                if path.is_file()
            )
            if draft_path.is_dir()
            else []
        )
        return value

    @staticmethod
    def _ready_documents(
        design: dict[str, Any],
        output: str,
    ) -> tuple[str, str]:
        plan_marker = "=== PLAN.md ==="
        handoff_marker = "=== IMPLEMENTATION_HANDOFF.md ==="
        if plan_marker in output and handoff_marker in output:
            _, remainder = output.split(plan_marker, 1)
            plan, handoff = remainder.split(handoff_marker, 1)
            if not handoff.strip():
                raise ValueError("Builder marked PLAN_READY without an implementation handoff")
            return plan.strip(), handoff.strip()
        plan = output.strip()
        return plan, HANDOFF_FALLBACK.format(
            requirement=design["requirement"],
            plan=plan,
        )

    async def _run(
        self,
        task: str,
        *,
        session_id: str,
        instructions: str,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> tuple[str, str]:
        client = self.client_factory(
            base_url or self.builder_base_url,
            api_key or self.builder_api_key,
        )
        run_id = await client.start_run(task=task, session_id=session_id, instructions=instructions)
        terminal: dict[str, Any] | None = None
        output_parts: list[str] = []
        async for event in client.events(run_id):
            if event.get("event") == "message.delta" and isinstance(event.get("delta"), str):
                output_parts.append(event["delta"])
            if str(event.get("event") or "").startswith("run."):
                terminal = event
        terminal = terminal or await client.status(run_id)
        status = str(terminal.get("status") or terminal.get("event", "")).removeprefix("run.")
        if status != "completed":
            raise RuntimeError(str(terminal.get("error") or f"Builder Run ended with {status}"))
        output = "".join(output_parts) or str(terminal.get("output") or "")
        if not output.strip():
            raise RuntimeError("Builder Run completed without a response")
        return output, run_id
