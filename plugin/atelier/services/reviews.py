from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from ..errors import AtelierError
from ..hermes_http import HermesHTTPClient
from ..paths import atelier_root, ensure_within, project_root
from ..redaction import redact
from ..schemas import ReviewRequest
from ..store import AtelierStore, now_iso
from .profiles import ProfileService
from .runs import event_type, final_output

REQUIRED_REVIEW_HEADINGS = (
    "OBSERVATIONS",
    "EVIDENCE",
    "HYPOTHESES",
    "PROPOSED_CHANGES",
    "RISKS",
    "VALIDATION_PLAN",
    "CONFIDENCE",
)


class ReviewService:
    def __init__(
        self,
        store: AtelierStore,
        *,
        profiles: ProfileService | None = None,
        client_factory: Any = HermesHTTPClient,
    ) -> None:
        self.store = store
        self.profiles = profiles or ProfileService(store)
        self.client_factory = client_factory
        self._tasks: set[asyncio.Task] = set()

    def create(self, request: ReviewRequest) -> dict[str, Any]:
        app = self.store.get_app(request.app_id)
        if app is None:
            raise KeyError(f"unknown application: {request.app_id}")
        for run_id in request.run_ids:
            run = self.store.get_run(run_id)
            if run is None or run["app_id"] != request.app_id:
                raise AtelierError("review_failed", f"Run does not belong to app: {run_id}")
        review = self.store.create_review(app_id=request.app_id, run_ids=request.run_ids)
        task = asyncio.create_task(self.execute(review["id"], request.feedback))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return review

    async def execute(self, review_id: str, feedback: str | None = None) -> dict[str, Any]:
        review = self.required(review_id)
        bundle = await self.freeze_bundle(review, feedback)
        try:
            self.profiles.restart("atelier-reviewer", terminal_cwd=bundle)
            base_url, key = self.profiles.endpoint_credentials("atelier-reviewer")
            client = self.client_factory(base_url, key)
            self.store.update_review(review_id, status="running")
            run_id = await client.start_run(
                task=(
                    f"Review the frozen Trace Bundle at {bundle}. Use only its evidence. "
                    "Write a review using exactly the required section headings and distinguish "
                    "事实, 推断, 建议, 尚缺证据. Do not modify the application or evaluation "
                    "criteria."
                ),
                session_id=review["reviewer_session_id"],
                instructions="You are the independent read-only atelier-reviewer.",
            )
            self.store.update_review(review_id, reviewer_hermes_run_id=run_id)
            terminal: dict[str, Any] | None = None
            output_parts: list[str] = []
            async for event in client.events(run_id):
                if event_type(event) == "message.delta" and isinstance(event.get("delta"), str):
                    output_parts.append(event["delta"])
                if event_type(event).startswith("run."):
                    terminal = event
            if terminal is None:
                terminal = await client.status(run_id)
            status = str(terminal.get("status") or event_type(terminal).removeprefix("run."))
            if status != "completed" and event_type(terminal) != "run.completed":
                raise AtelierError("review_failed", str(terminal.get("error") or status))
            output = "".join(output_parts) or final_output(terminal)
            self._validate_output(output)
            result_path = atelier_root() / "reviews" / review_id / "result.md"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(output, encoding="utf-8")
            self.store.update_review(
                review_id, status="completed", result_path=str(result_path), ended_at=now_iso()
            )
        except Exception as exc:
            self.store.update_review(
                review_id, status="review_failed", error_type="review_failed", ended_at=now_iso()
            )
            error_path = atelier_root() / "reviews" / review_id / "error.txt"
            error_path.parent.mkdir(parents=True, exist_ok=True)
            error_path.write_text(str(exc)[:2000], encoding="utf-8")
        return self.required(review_id)

    async def freeze_bundle(self, review: dict[str, Any], additional_feedback: str | None) -> Path:
        bundle = atelier_root() / "trace-bundles" / review["id"]
        if bundle.exists():
            return bundle
        bundle.mkdir(parents=True)
        app = self.store.get_app(review["app_id"])
        if app is None:
            raise AtelierError("review_failed", "application disappeared during review")
        runs = [self.store.get_run(run_id) for run_id in review["run_ids"]]
        if any(run is None for run in runs):
            raise AtelierError("review_failed", "selected Run disappeared during review")
        manifest = {
            "schema_version": 1,
            "review_id": review["id"],
            "app_id": review["app_id"],
            "run_ids": review["run_ids"],
            "created_at": now_iso(),
            "definition_revision": app["definition_revision"],
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with (bundle / "events.jsonl").open("w", encoding="utf-8") as output:
            for run_id in review["run_ids"]:
                for event in self.store.list_events(run_id):
                    output.write(json.dumps(redact(event), ensure_ascii=False) + "\n")
        feedback = {
            "additional_feedback": additional_feedback,
            "runs": {run_id: self.store.get_feedback(run_id) for run_id in review["run_ids"]},
        }
        (bundle / "feedback.json").write_text(
            json.dumps(redact(feedback), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        source = ensure_within(Path(app["source_path"]), project_root() / "apps")
        shutil.copytree(source, bundle / "app-definition")
        sessions_dir = bundle / "sessions"
        sessions_dir.mkdir()
        session_refs: set[tuple[str, str]] = set()
        for run in runs:
            session_refs.add((run["root_profile"], run["root_session_id"]))
            for span in self.store.list_spans(run["id"]):
                session_refs.add((span["target_profile"], span["target_session_id"]))
        session_errors = []
        for profile, session_id in sorted(session_refs):
            try:
                base_url, key = self.profiles.endpoint_credentials(profile)
                messages = await self.client_factory(base_url, key).session_messages(session_id)
                payload: Any = redact(messages)
            except Exception as exc:
                payload = {"error": "session_unavailable", "message": str(exc)[:500]}
                session_errors.append(f"{profile}:{session_id}")
            (sessions_dir / f"{profile}--{session_id}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        result_lines = ["# Run Results", ""]
        for run in runs:
            result_lines.extend(
                [
                    f"## {run['id']}",
                    "",
                    f"Status: {run['status']}",
                    "",
                    run.get("output_text") or "(no output)",
                    "",
                ]
            )
        if session_errors:
            result_lines.extend(
                ["## Trace degradation", "", "Unavailable Sessions: " + ", ".join(session_errors)]
            )
        (bundle / "result.md").write_text("\n".join(result_lines), encoding="utf-8")
        return bundle

    def detail(self, review_id: str) -> dict[str, Any]:
        review = self.required(review_id)
        value = dict(review)
        if review.get("result_path") and Path(review["result_path"]).is_file():
            value["result"] = Path(review["result_path"]).read_text(encoding="utf-8")
        else:
            value["result"] = None
        value["trace_bundle"] = str(atelier_root() / "trace-bundles" / review_id)
        return value

    def required(self, review_id: str) -> dict[str, Any]:
        review = self.store.get_review(review_id)
        if review is None:
            raise KeyError(f"unknown Review: {review_id}")
        return review

    @staticmethod
    def _validate_output(output: str) -> None:
        positions = [output.find(heading) for heading in REQUIRED_REVIEW_HEADINGS]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            raise AtelierError(
                "review_failed", "Reviewer output is missing required ordered sections"
            )
