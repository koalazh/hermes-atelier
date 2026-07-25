from __future__ import annotations

from typing import Any

from .cli_v2 import run_cli_namespace, setup_cli_parser


def register(ctx: Any) -> None:
    ctx.register_cli_command(
        name="atelier",
        help="Design, observe, evaluate, and release Hermes App Packs",
        description="V2 development workbench; never an application runtime dependency",
        setup_fn=setup_cli_parser,
        handler_fn=run_cli_namespace,
    )
