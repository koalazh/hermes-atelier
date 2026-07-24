from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from .services.apps import AppService
from .services.profiles import ProfileService
from .services.runs import RunService
from .store import AtelierStore


def setup_cli_parser(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="atelier_action", required=True)
    commands.add_parser("bootstrap", help="Initialize the project-local Hermes root")
    commands.add_parser("apps", help="List registered applications")
    status = commands.add_parser("status", help="Show Profile endpoint state")
    status.add_argument("app_id", nargs="?")
    for action in ("start", "stop", "restart"):
        item = commands.add_parser(action, help=f"{action.title()} an application")
        item.add_argument("app_id")
    smoke = commands.add_parser("smoke", help="Run one input through an application's entry Agent")
    smoke.add_argument("app_id")
    smoke.add_argument("input")


def run_cli_namespace(args: argparse.Namespace) -> int:
    store = AtelierStore()
    app_service = AppService(store)
    profile_service = ProfileService(store)
    action = args.atelier_action
    if action == "bootstrap":
        profile_service.bootstrap_root()
        registered = app_service.register_all()
        print(json.dumps({"apps": [app["id"] for app in registered]}, indent=2))
        return 0
    if action == "apps":
        print(json.dumps(app_service.list(), indent=2))
        return 0
    if action == "status":
        print(json.dumps(store.list_endpoints(args.app_id), indent=2))
        return 0
    definition = app_service.get_definition(args.app_id)
    if action in {"start", "stop", "restart"}:
        operation = getattr(profile_service, action)
        print(json.dumps([operation(profile.name) for profile in definition.profiles], indent=2))
        return 0
    if action == "smoke":
        service = RunService(store, profile_service=profile_service, app_service=app_service)

        async def execute() -> dict[str, Any]:
            run = store.create_run(
                app_id=args.app_id,
                scenario_id="cli-smoke",
                root_profile=definition.entry_profile,
                definition_revision=store.get_app(args.app_id)["definition_revision"],
                input_text=args.input,
                memory_scope=None,
                user_label="CLI smoke",
            )
            return await service.execute_root(run["id"])

        print(json.dumps(asyncio.run(execute()), indent=2))
        return 0
    raise ValueError(f"unknown action: {action}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atelier")
    setup_cli_parser(parser)
    return run_cli_namespace(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
