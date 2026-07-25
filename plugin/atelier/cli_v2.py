from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app_pack import AppPack, build_definition_snapshot, release_pack
from .evaluation import load_case
from .paths import atelier_root
from .studio_store import StudioStore


def setup_cli_parser(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="atelier_action", required=True)
    validate = commands.add_parser("validate", help="Validate one Hermes App Pack")
    validate.add_argument("pack", type=Path)
    release = commands.add_parser("release", help="Create an immutable App Pack release")
    release.add_argument("pack", type=Path)
    release.add_argument("destination", type=Path)
    release.add_argument("--git-revision")
    cases = commands.add_parser("cases", help="List validated Cases in one App Pack")
    cases.add_argument("pack", type=Path)
    commands.add_parser("designs", help="List V2 Design records")
    commands.add_parser("experiments", help="List V2 Experiment records")


def run_cli_namespace(args: argparse.Namespace) -> int:
    action = args.atelier_action
    if action in {"designs", "experiments"}:
        store = StudioStore(atelier_root() / "v2")
        values = store.list_designs() if action == "designs" else store.list_experiments()
        print(json.dumps(values, indent=2, ensure_ascii=False))
        return 0
    pack = AppPack.load(args.pack)
    if action == "validate":
        print(json.dumps(build_definition_snapshot(pack), indent=2, ensure_ascii=False))
        return 0
    if action == "release":
        result = release_pack(pack, args.destination, git_revision=args.git_revision)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if action == "cases":
        result = []
        for relative in pack.manifest.cases:
            case, digest = load_case(pack.root / relative)
            result.append({**case.model_dump(mode="json"), "hash": digest})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    raise ValueError(f"unknown action: {action}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atelier")
    setup_cli_parser(parser)
    return run_cli_namespace(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
