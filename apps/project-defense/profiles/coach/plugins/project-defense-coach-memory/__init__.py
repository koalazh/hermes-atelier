from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]

SCOPE_SESSION_RE = re.compile(r"^pcms_([0-9a-f]{24})_[0-9a-f]{32}$")
MAX_ENTRY_CHARS = 500
MAX_ENTRIES = 50
SCHEMA = {
    "name": "defense_coach_memory",
    "description": (
        "Read or update durable coaching preferences in the caller scope selected by "
        "profile_call. Clean calls have no durable scope and cannot access this state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "remove"]},
            "content": {"type": "string", "maxLength": MAX_ENTRY_CHARS},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


def _root() -> Path:
    configured = os.environ.get("DEFENSE_COACH_MEMORY_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    try:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    except ImportError:
        home = Path(os.environ.get("HERMES_HOME", "."))
    return (home / "local" / "project-defense-coach-memory").resolve()


def _scope_id(session_id: str) -> str:
    match = SCOPE_SESSION_RE.fullmatch(session_id)
    if not match:
        raise ValueError("no retained caller scope is available for this Coach call")
    return match.group(1)


def _path(scope_id: str) -> Path:
    return _root() / f"{scope_id}.json"


def _load(path: Path) -> list[str]:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("invalid scoped coaching memory")
    return value


def _save(path: Path, entries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    with lock.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _operate(args: dict[str, Any], *, session_id: str) -> dict[str, Any]:
    scope_id = _scope_id(session_id)
    path = _path(scope_id)
    with _locked(path):
        entries = _load(path)
        action = str(args.get("action") or "")
        if action == "list":
            return {"ok": True, "scope_id": scope_id, "entries": entries}
        content = str(args.get("content") or "").strip()
        if not content:
            raise ValueError(f"{action} requires content")
        if len(content) > MAX_ENTRY_CHARS:
            raise ValueError("coaching preference is too long")
        if action == "add":
            if content not in entries:
                if len(entries) >= MAX_ENTRIES:
                    raise ValueError("scoped coaching memory is full")
                entries.append(content)
                _save(path, entries)
            return {"ok": True, "scope_id": scope_id, "stored": True, "entries": entries}
        if action == "remove":
            if content in entries:
                entries.remove(content)
                _save(path, entries)
            return {"ok": True, "scope_id": scope_id, "removed": True, "entries": entries}
        raise ValueError("unsupported coaching memory action")


def register(ctx: Any) -> None:
    def handler(args: dict[str, Any], session_id: str = "", **_: Any) -> str:
        try:
            result = _operate(args, session_id=session_id)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        return json.dumps(result, ensure_ascii=False)

    ctx.register_tool(
        name="defense_coach_memory",
        toolset="project-defense-coach-memory",
        schema=SCHEMA,
        handler=handler,
        description="Caller-scoped Project Defense coaching preferences",
        emoji="🧭",
    )
