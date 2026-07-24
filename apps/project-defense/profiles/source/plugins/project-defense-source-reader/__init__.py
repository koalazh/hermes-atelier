from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MAX_RESULT_CHARS = 40_000
SCHEMA = {
    "name": "defense_source_read",
    "description": "List, read, or literal-search the declared read-only source workspace.",
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["list", "read", "search"]},
            "path": {"type": "string", "default": "."},
            "query": {"type": "string"},
        },
        "required": ["operation"],
        "additionalProperties": False,
    },
}


def _workspace() -> Path:
    root = Path(os.environ["ATELIER_PROJECT_ROOT"]).resolve()
    return (root / "apps" / "project-defense" / "sample-source").resolve()


def _safe_path(relative: str) -> Path:
    root = _workspace()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes the declared source workspace") from exc
    return candidate


def _read(args: dict[str, Any]) -> dict[str, Any]:
    operation = str(args["operation"])
    relative = str(args.get("path") or ".")
    path = _safe_path(relative)
    if operation == "list":
        if not path.is_dir():
            raise ValueError("list path is not a directory")
        entries = [item.relative_to(_workspace()).as_posix() for item in sorted(path.iterdir())]
        return {"operation": operation, "path": relative, "entries": entries}
    if operation == "read":
        if not path.is_file():
            raise ValueError("read path is not a file")
        lines = path.read_text(encoding="utf-8").splitlines()
        numbered = "\n".join(f"{index}: {line}" for index, line in enumerate(lines, 1))
        return {"operation": operation, "path": relative, "content": numbered[:MAX_RESULT_CHARS]}
    if operation == "search":
        query = str(args.get("query") or "")
        if not query:
            raise ValueError("search requires query")
        base = path if path.is_dir() else path.parent
        matches = []
        for file_path in sorted(base.rglob("*")):
            if not file_path.is_file() or file_path.is_symlink():
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, 1):
                if query in line:
                    matches.append(
                        {
                            "path": file_path.relative_to(_workspace()).as_posix(),
                            "line": line_number,
                            "text": line[:500],
                        }
                    )
        return {"operation": operation, "query": query, "matches": matches[:100]}
    raise ValueError("unsupported read operation")


def register(ctx: Any) -> None:
    def handler(args: dict[str, Any], **_: Any) -> str:
        return json.dumps(_read(args), ensure_ascii=False)

    ctx.register_tool(
        name="defense_source_read",
        toolset="project-defense-source",
        schema=SCHEMA,
        handler=handler,
        description="Constrained read-only Project Defense source access",
        emoji="🔍",
    )
