from __future__ import annotations

import json
from typing import Any

from .cli import run_cli_namespace, setup_cli_parser
from .services.runs import RunService
from .store import AtelierStore

ATELIER_CALL_SCHEMA = {
    "name": "atelier_call",
    "description": (
        "Call one allowlisted Hermes Profile as a real child Agent. You decide whether to call, "
        "which target to use, ordering, sufficiency, and how to combine results."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Exact target Hermes Profile name from the application allowlist.",
            },
            "task": {
                "type": "string",
                "description": "A complete task for the target Agent, including required output.",
            },
            "memory_scope": {
                "type": "string",
                "description": "Optional stable business/entity scope for long-term Memory.",
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


def register(ctx: Any) -> None:
    source_profile = ctx.profile_name
    service = RunService(AtelierStore())

    async def atelier_call_handler(
        args: dict[str, Any],
        task_id: str = "",
        session_id: str = "",
        **_: Any,
    ) -> str:
        return json.dumps(
            await service.call(
                args,
                source_profile=source_profile,
                task_id=task_id,
                session_id=session_id,
            ),
            ensure_ascii=False,
        )

    ctx.register_tool(
        name="atelier_call",
        toolset="atelier",
        schema=ATELIER_CALL_SCHEMA,
        handler=atelier_call_handler,
        is_async=True,
        description="Observable allowlisted cross-Profile Hermes Agent call",
        emoji="⚗️",
    )
    ctx.register_cli_command(
        name="atelier",
        help="Project-local Hermes multi-Agent development workbench",
        description="Build, run, observe, review, approve, and replay Profile applications",
        setup_fn=setup_cli_parser,
        handler_fn=run_cli_namespace,
    )
