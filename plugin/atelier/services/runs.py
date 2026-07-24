from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from ..errors import AtelierError, normalize_error
from ..hermes_http import HermesHTTPClient
from ..redaction import redact_text
from ..schemas import AppDefinition, AtelierCallInput, RunRequest
from ..store import AtelierStore, now_iso
from .apps import AppService
from .profiles import ProfileService

SESSION_RE = re.compile(r"^at_([0-9a-f]{32})_(root|[0-9a-f]{32})$")
TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled"}


def parse_atelier_session(session_id: str) -> tuple[str, str | None]:
    match = SESSION_RE.fullmatch(session_id)
    if not match:
        raise AtelierError(
            "invalid_session", "atelier_call requires an Atelier-created Hermes session"
        )
    run_id, suffix = match.groups()
    return run_id, None if suffix == "root" else suffix


def event_type(event: dict[str, Any]) -> str:
    value = event.get("event") or event.get("type") or "unknown"
    return str(value)


def final_output(event: dict[str, Any]) -> str:
    output = event.get("output")
    if isinstance(output, str):
        return output
    response = event.get("response")
    if isinstance(response, dict):
        output = response.get("output_text") or response.get("output")
        if isinstance(output, str):
            return output
    return ""


class RunService:
    def __init__(
        self,
        store: AtelierStore,
        *,
        profile_service: ProfileService | None = None,
        app_service: AppService | None = None,
        client_factory: Any = HermesHTTPClient,
    ) -> None:
        self.store = store
        self.profiles = profile_service or ProfileService(store)
        self.apps = app_service or AppService(store)
        self.client_factory = client_factory
        self._tasks: set[asyncio.Task] = set()

    def start_root(self, request: RunRequest) -> dict[str, Any]:
        app = self.store.get_app(request.app_id)
        if app is None:
            raise KeyError(f"unknown application: {request.app_id}")
        run = self.store.create_run(
            app_id=request.app_id,
            scenario_id=request.scenario_id,
            root_profile=app["entry_profile"],
            definition_revision=app["definition_revision"],
            input_text=request.input,
            memory_scope=request.memory_scope,
            user_label=request.user_label,
        )
        task = asyncio.create_task(self.execute_root(run["id"]))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return run

    async def execute_root(self, run_id: str) -> dict[str, Any]:
        run = self._required_run(run_id)
        base_url, key = self.profiles.endpoint_credentials(run["root_profile"])
        client = self.client_factory(base_url, key)
        trace_degraded = False
        try:
            self.store.update_run(run_id, status="running")
            hermes_run_id = await client.start_run(
                task=run["input_text"],
                session_id=run["root_session_id"],
                memory_scope=run["memory_scope"],
            )
            self.store.update_run(run_id, root_hermes_run_id=hermes_run_id)
            terminal: dict[str, Any] | None = None
            try:
                async for event in client.events(hermes_run_id):
                    terminal = event if event_type(event) in TERMINAL_EVENTS else terminal
                    try:
                        self.store.add_event(
                            atelier_run_id=run_id,
                            span_id=None,
                            profile=run["root_profile"],
                            hermes_run_id=hermes_run_id,
                            event_type=event_type(event),
                            timestamp=event.get("timestamp"),
                            payload=event,
                        )
                    except Exception:
                        trace_degraded = True
            except AtelierError as exc:
                if exc.error_type != "trace_degraded":
                    raise
                trace_degraded = True
                terminal = await client.status(hermes_run_id)
            if terminal is None:
                terminal = await client.status(hermes_run_id)
            status = str(terminal.get("status") or event_type(terminal).removeprefix("run."))
            output = final_output(terminal) or str(terminal.get("output") or "")
            if status == "completed" or event_type(terminal) == "run.completed":
                self.store.update_run(
                    run_id,
                    status="trace_degraded" if trace_degraded else "completed",
                    output_text=output,
                    error_type="trace_degraded" if trace_degraded else None,
                    ended_at=now_iso(),
                )
            elif status == "cancelled" or event_type(terminal) == "run.cancelled":
                self.store.update_run(
                    run_id, status="cancelled", error_type="child_cancelled", ended_at=now_iso()
                )
            else:
                self.store.update_run(
                    run_id,
                    status="failed",
                    error_type="root_run_failed",
                    ended_at=now_iso(),
                )
        except Exception as exc:
            try:
                self.store.update_run(
                    run_id,
                    status="failed",
                    error_type=(
                        exc.error_type if isinstance(exc, AtelierError) else "root_run_failed"
                    ),
                    ended_at=now_iso(),
                )
            except Exception:
                pass
            raise
        return self._required_run(run_id)

    async def call(
        self,
        args: dict[str, Any],
        *,
        source_profile: str,
        task_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        try:
            request = AtelierCallInput.model_validate(args)
        except Exception as exc:
            return AtelierError("child_call_failed", f"invalid atelier_call input: {exc}").as_dict()
        if not task_id or not session_id or task_id != session_id:
            return AtelierError(
                "incompatible_hermes",
                "Hermes did not provide a stable matching task_id and session_id; "
                "Hermes >=0.19.0 is required",
            ).as_dict()
        try:
            run_id, parent_span_id = parse_atelier_session(session_id)
            run = self._required_run(run_id)
            self._validate_source(run, parent_span_id, source_profile, session_id)
            definition = AppDefinition.model_validate(
                json.loads(self.store.get_app(run["app_id"])["definition_json"])
            )
            if not definition.allows(source_profile, request.target):
                raise AtelierError(
                    "call_not_allowed",
                    f"{source_profile} is not allowed to call {request.target}",
                )
            span = self.store.create_span(
                atelier_run_id=run_id,
                parent_span_id=parent_span_id,
                source_profile=source_profile,
                target_profile=request.target,
                source_session_id=session_id,
                request_summary=redact_text(request.task[:2000]),
            )
        except Exception as exc:
            return normalize_error(exc, "trace_degraded")

        base_url, key = self.profiles.endpoint_credentials(request.target)
        client = self.client_factory(base_url, key)
        trace_degraded = False
        hermes_run_id: str | None = None
        try:
            async with asyncio.timeout(request.timeout_seconds):
                hermes_run_id = await client.start_run(
                    task=request.task,
                    session_id=span["target_session_id"],
                    memory_scope=request.memory_scope,
                )
                self.store.update_span(
                    span["id"], status="running", target_hermes_run_id=hermes_run_id
                )
                terminal: dict[str, Any] | None = None
                try:
                    async for event in client.events(hermes_run_id):
                        if event_type(event) in TERMINAL_EVENTS:
                            terminal = event
                        try:
                            self.store.add_event(
                                atelier_run_id=run_id,
                                span_id=span["id"],
                                profile=request.target,
                                hermes_run_id=hermes_run_id,
                                event_type=event_type(event),
                                timestamp=event.get("timestamp"),
                                payload=event,
                            )
                        except Exception:
                            trace_degraded = True
                except AtelierError as exc:
                    if exc.error_type != "trace_degraded":
                        raise
                    trace_degraded = True
                    terminal = await client.status(hermes_run_id)
                if terminal is None:
                    terminal = await client.status(hermes_run_id)
                terminal_type = event_type(terminal)
                status = str(terminal.get("status") or terminal_type.removeprefix("run."))
                output = final_output(terminal) or str(terminal.get("output") or "")
                if status == "completed" or terminal_type == "run.completed":
                    self.store.update_span(
                        span["id"],
                        status="trace_degraded" if trace_degraded else "completed",
                        response_summary=redact_text(output[:4000]),
                        error_type="trace_degraded" if trace_degraded else None,
                        ended_at=now_iso(),
                    )
                    return {
                        "ok": True,
                        "target": request.target,
                        "result": output,
                        "atelier_run_id": run_id,
                        "span_id": span["id"],
                        "target_session_id": span["target_session_id"],
                        "target_hermes_run_id": hermes_run_id,
                        "trace_degraded": trace_degraded,
                    }
                error_type = (
                    "child_cancelled"
                    if status == "cancelled" or terminal_type == "run.cancelled"
                    else "child_call_failed"
                )
                message = str(terminal.get("error") or f"child run ended with {status}")
                self.store.update_span(
                    span["id"], status="failed", error_type=error_type, ended_at=now_iso()
                )
                return AtelierError(error_type, redact_text(message)).as_dict()
        except TimeoutError:
            if hermes_run_id:
                try:
                    await client.stop(hermes_run_id)
                except Exception:
                    pass
            self.store.update_span(
                span["id"], status="timeout", error_type="child_timeout", ended_at=now_iso()
            )
            return AtelierError(
                "child_timeout",
                f"child run timed out after {request.timeout_seconds} seconds; stop was requested",
            ).as_dict()
        except Exception as exc:
            try:
                self.store.update_span(
                    span["id"], status="failed", error_type="child_call_failed", ended_at=now_iso()
                )
            except Exception:
                pass
            return normalize_error(exc, "child_call_failed")

    async def stop(self, run_id: str) -> dict[str, Any]:
        run = self._required_run(run_id)
        self.store.update_run(run_id, status="stopping")
        requests: list[tuple[str, str]] = []
        if run.get("root_hermes_run_id"):
            requests.append((run["root_profile"], run["root_hermes_run_id"]))
        for span in self.store.list_spans(run_id):
            if span["status"] in {"queued", "running", "trace_degraded"} and span.get(
                "target_hermes_run_id"
            ):
                requests.append((span["target_profile"], span["target_hermes_run_id"]))
        results = []
        for profile, hermes_run_id in requests:
            try:
                base_url, key = self.profiles.endpoint_credentials(profile)
                results.append(await self.client_factory(base_url, key).stop(hermes_run_id))
            except Exception as exc:
                results.append(normalize_error(exc, "child_cancelled"))
        return {"run_id": run_id, "status": "stopping", "stop_requests": results}

    def detail(self, run_id: str) -> dict[str, Any]:
        run = self._required_run(run_id)
        run["spans"] = self.store.list_spans(run_id)
        run["feedback"] = self.store.get_feedback(run_id)
        return run

    def _required_run(self, run_id: str) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown Atelier run: {run_id}")
        return run

    def _validate_source(
        self,
        run: dict[str, Any],
        parent_span_id: str | None,
        source_profile: str,
        session_id: str,
    ) -> None:
        if parent_span_id is None:
            if run["root_session_id"] != session_id or run["root_profile"] != source_profile:
                raise AtelierError("invalid_session", "root caller identity does not match run")
            return
        parent = self.store.get_span(parent_span_id)
        if (
            parent is None
            or parent["atelier_run_id"] != run["id"]
            or parent["target_session_id"] != session_id
            or parent["target_profile"] != source_profile
        ):
            raise AtelierError(
                "invalid_session", "child caller identity does not match parent Span"
            )
