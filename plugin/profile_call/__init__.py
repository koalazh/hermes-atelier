from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

PROFILE_CALL_SCHEMA = {
    "name": "profile_call",
    "description": (
        "Call one allowlisted logical Hermes Agent. You decide whether to call, which target "
        "to use, ordering, sufficiency, and how to combine the returned evidence."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Logical Agent ID from this App Pack's allowed_calls boundary.",
            },
            "task": {
                "type": "string",
                "description": "Complete task and required output for the target Agent.",
            },
            "memory_scope": {
                "type": "string",
                "description": "Optional explicit stable scope for retained target Memory.",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 1,
                "maximum": 900,
                "default": 120,
            },
        },
        "required": ["target", "task"],
        "additionalProperties": False,
    },
}


class ProfileCallError(RuntimeError):
    def __init__(self, message: str, *, stop_status: str | None = None) -> None:
        super().__init__(message)
        self.stop_status = stop_status


def _runtime_path() -> Path:
    configured = os.environ.get("PROFILE_CALL_RUNTIME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    try:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    except ImportError:
        home = Path(os.environ.get("HERMES_HOME", "."))
    return (home / "local" / "app-runtime.json").resolve()


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event") or event.get("type") or "unknown")


def _event_output(event: dict[str, Any]) -> str:
    output = event.get("output")
    if isinstance(output, str):
        return output
    response = event.get("response")
    if isinstance(response, dict):
        nested = response.get("output_text") or response.get("output")
        if isinstance(nested, str):
            return nested
    return ""


class ProfileCaller:
    def __init__(
        self,
        *,
        runtime_path: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        trace_transport: httpx.AsyncBaseTransport | None = None,
        trace_timeout: float = 0.2,
        stop_timeout: float = 2.0,
    ) -> None:
        self.runtime_path = (runtime_path or _runtime_path()).resolve()
        self.transport = transport
        self.trace_transport = trace_transport or transport
        self.trace_timeout = trace_timeout
        self.stop_timeout = stop_timeout

    def runtime(self) -> dict[str, Any]:
        if not self.runtime_path.is_file():
            raise ProfileCallError(f"profile_call runtime mapping is missing: {self.runtime_path}")
        try:
            value = json.loads(self.runtime_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileCallError(f"invalid profile_call runtime mapping: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ProfileCallError("unsupported profile_call runtime mapping")
        return value

    async def call(
        self,
        args: dict[str, Any],
        *,
        source_session_id: str = "",
        task_id: str = "",
    ) -> dict[str, Any]:
        runtime = self.runtime()
        source = str(runtime.get("current_agent") or "")
        target = str(args.get("target") or "").strip()
        task = str(args.get("task") or "").strip()
        if not source or not target or not task:
            raise ProfileCallError("profile_call requires current_agent, target, and task")
        allowed = runtime.get("allowed_calls", {}).get(source, [])
        if target not in allowed:
            raise ProfileCallError(f"{source} is not allowed to call {target}")
        target_config = runtime.get("agents", {}).get(target)
        if not isinstance(target_config, dict):
            raise ProfileCallError(f"logical target is not mapped: {target}")
        base_url = str(target_config.get("base_url") or "").rstrip("/")
        profile = str(target_config.get("profile") or "")
        key_env = str(target_config.get("api_key_env") or "")
        api_key = os.environ.get(key_env, "") if key_env else ""
        if not base_url or not profile or not api_key:
            raise ProfileCallError(f"incomplete runtime mapping for {target}")

        call_id = uuid.uuid4().hex
        memory_scope = args.get("memory_scope")
        memory_scope_id = (
            hashlib.sha256(str(memory_scope).encode()).hexdigest()[:24]
            if memory_scope
            else None
        )
        target_session_id = (
            f"pcms_{memory_scope_id}_{call_id}" if memory_scope_id else f"pc_{call_id}"
        )
        timeout = int(args.get("timeout_seconds") or 120)
        if timeout < 1 or timeout > 900:
            raise ProfileCallError("timeout_seconds must be between 1 and 900")
        headers = {"Authorization": f"Bearer {api_key}"}
        if memory_scope:
            headers["X-Hermes-Session-Key"] = str(memory_scope)
        trace_degraded = False
        trace = runtime.get("trace") if isinstance(runtime.get("trace"), dict) else None
        started = {
            "event": "profile_call.started",
            "call_id": call_id,
            "source": source,
            "target": target,
            "source_session_id": source_session_id or None,
            "target_session_id": target_session_id,
            "task_id": task_id or None,
            "memory_scope_id": memory_scope_id,
        }
        async with (
            httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                transport=self.transport,
            ) as client,
            httpx.AsyncClient(
                timeout=httpx.Timeout(self.trace_timeout),
                transport=self.trace_transport,
            ) as trace_client,
        ):
            if trace and not await self._emit_trace(trace_client, trace, started):
                trace_degraded = True
            response = await client.post(
                f"{base_url}/v1/runs",
                headers=headers,
                json={"input": task, "session_id": target_session_id},
            )
            response.raise_for_status()
            run_id = str(response.json().get("run_id") or "")
            if not run_id:
                raise ProfileCallError("Hermes did not return a run_id")
            try:
                async with asyncio.timeout(timeout):
                    terminal: dict[str, Any] | None = None
                    async with client.stream(
                        "GET", f"{base_url}/v1/runs/{run_id}/events", headers=headers
                    ) as stream:
                        stream.raise_for_status()
                        async for line in stream.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            raw = line.removeprefix("data:").strip()
                            if not raw:
                                continue
                            event = json.loads(raw)
                            if not isinstance(event, dict):
                                raise ProfileCallError("Hermes emitted a non-object SSE event")
                            if _event_type(event) in {
                                "run.completed",
                                "run.failed",
                                "run.cancelled",
                            }:
                                terminal = event
                    if terminal is None:
                        response = await client.get(
                            f"{base_url}/v1/runs/{run_id}", headers=headers
                        )
                        response.raise_for_status()
                        terminal = response.json()
                        if not isinstance(terminal, dict):
                            raise ProfileCallError("Hermes returned an invalid run status")
            except asyncio.CancelledError:
                await self._stop_cancelled_call(client, base_url, headers, run_id)
                raise
            except Exception as exc:
                stop_status = await self._best_effort_stop(
                    client, base_url, headers, run_id
                )
                raise ProfileCallError(str(exc), stop_status=stop_status) from exc
            status = str(
                terminal.get("status") or _event_type(terminal).removeprefix("run.")
            )
            completed = status == "completed" or _event_type(terminal) == "run.completed"
            output = _event_output(terminal)
            finished = {
                **started,
                "event": "profile_call.completed" if completed else "profile_call.failed",
                "target_hermes_run_id": run_id,
                "status": status,
                "result": output,
                "error": terminal.get("error"),
            }
            if trace and not await self._emit_trace(trace_client, trace, finished):
                trace_degraded = True
        if not completed:
            raise ProfileCallError(str(terminal.get("error") or f"target run ended with {status}"))
        result = {
            "ok": True,
            "target": target,
            "target_profile": profile,
            "result": output,
            "source_session_id": source_session_id or None,
            "target_session_id": target_session_id,
            "target_hermes_run_id": run_id,
            "call_id": call_id,
            "trace_degraded": trace_degraded,
        }
        if memory_scope_id:
            result["memory_scope_id"] = memory_scope_id
        return result

    async def _emit_trace(
        self,
        client: httpx.AsyncClient,
        trace: dict[str, Any],
        event: dict[str, Any],
    ) -> bool:
        emitted = True
        file_name = str(trace.get("file") or "")
        directory_name = str(trace.get("directory") or "")
        if directory_name:
            source_session_id = str(event.get("source_session_id") or event["call_id"])
            name = hashlib.sha256(source_session_id.encode()).hexdigest() + ".jsonl"
            file_name = str(Path(directory_name).expanduser().resolve() / name)
        if file_name:
            try:
                path = Path(file_name).expanduser().resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                line = (json.dumps(event, ensure_ascii=False) + "\n").encode()
                descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
                try:
                    os.write(descriptor, line)
                finally:
                    os.close(descriptor)
            except OSError:
                emitted = False
        url = str(trace.get("url") or "")
        if not url:
            return emitted
        headers: dict[str, str] = {}
        token_env = str(trace.get("token_env") or "")
        token = os.environ.get(token_env, "") if token_env else ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = await asyncio.wait_for(
                client.post(url, headers=headers, json=event),
                timeout=self.trace_timeout,
            )
            response.raise_for_status()
            return emitted
        except (TimeoutError, httpx.HTTPError, OSError):
            return False

    async def _best_effort_stop(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        run_id: str,
    ) -> str:
        try:
            response = await asyncio.wait_for(
                client.post(
                    f"{base_url}/v1/runs/{run_id}/stop",
                    headers=headers,
                    json={},
                ),
                timeout=self.stop_timeout,
            )
            if response.status_code not in {200, 202}:
                return "stop_unknown"
            payload = response.json()
            status = str(payload.get("status") or "") if isinstance(payload, dict) else ""
            if status in {"cancelled", "canceled", "completed", "failed"}:
                return "stop_confirmed"
            return "stop_requested"
        except (TimeoutError, httpx.HTTPError, OSError, ValueError):
            return "stop_unknown"

    async def _stop_cancelled_call(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        run_id: str,
    ) -> None:
        task = asyncio.create_task(self._best_effort_stop(client, base_url, headers, run_id))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            pass


def register(ctx: Any) -> None:
    caller = ProfileCaller()

    async def profile_call_handler(
        args: dict[str, Any], task_id: str = "", session_id: str = "", **_: Any
    ) -> str:
        try:
            result = await caller.call(
                args,
                source_session_id=session_id,
                task_id=task_id,
            )
        except Exception as exc:
            result = {"ok": False, "error_type": "profile_call_failed", "message": str(exc)}
            stop_status = getattr(exc, "stop_status", None)
            if stop_status:
                result["stop_status"] = stop_status
        return json.dumps(result, ensure_ascii=False)

    ctx.register_tool(
        name="profile_call",
        toolset="profile_call",
        schema=PROFILE_CALL_SCHEMA,
        handler=profile_call_handler,
        is_async=True,
        description="Logical allowlisted Hermes Agent call",
        emoji="↗️",
    )
