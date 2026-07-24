from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.services.apps import AppService  # noqa: E402
from plugin.atelier.services.profiles import ProfileService  # noqa: E402
from plugin.atelier.services.runs import RunService  # noqa: E402
from plugin.atelier.store import AtelierStore  # noqa: E402


async def execute(app_id: str, scenario: str | None) -> dict:
    store = AtelierStore()
    apps = AppService(store)
    profiles = ProfileService(store)
    definition = apps.get_definition(app_id)
    scenario_dir = Path(store.get_app(app_id)["source_path"]) / definition.scenarios_dir
    if scenario:
        scenario_path = scenario_dir / scenario
    else:
        candidates = sorted(scenario_dir.glob("*.yaml"))
        if not candidates:
            raise RuntimeError(f"no YAML smoke scenario for {app_id}")
        scenario_path = candidates[0]
    import yaml

    payload = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    prompt = payload["input"]
    run = store.create_run(
        app_id=app_id,
        scenario_id=scenario_path.stem,
        root_profile=definition.entry_profile,
        definition_revision=store.get_app(app_id)["definition_revision"],
        input_text=prompt,
        memory_scope=payload.get("memory_scope"),
        user_label="smoke",
    )
    return await RunService(store, profile_service=profiles, app_service=apps).execute_root(
        run["id"]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a real Hermes Atelier smoke scenario")
    parser.add_argument("app_id")
    parser.add_argument("--scenario")
    args = parser.parse_args(argv)
    result = asyncio.run(execute(args.app_id, args.scenario))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"completed", "trace_degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

