from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.services.apps import AppService  # noqa: E402
from plugin.atelier.services.profiles import ProfileService  # noqa: E402
from plugin.atelier.store import AtelierStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start Atelier Profile Gateways")
    parser.add_argument("--app", action="append", default=[])
    parser.add_argument("--dashboard", action="store_true")
    parser.add_argument("--dashboard-host", default="127.0.0.1")
    parser.add_argument("--dashboard-port", type=int, default=9119)
    args = parser.parse_args(argv)
    if args.dashboard_host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Atelier V1 refuses non-loopback Dashboard binding")
    store = AtelierStore()
    apps = AppService(store)
    profiles = ProfileService(store)
    names = ["atelier-builder", "atelier-reviewer"]
    selected = set(args.app)
    for app in apps.list():
        if not selected or app["id"] in selected:
            names.extend(profile.name for profile in apps.get_definition(app["id"]).profiles)
    for name in dict.fromkeys(names):
        profiles.start(name)
        print(f"started {name}")
    if args.dashboard:
        environment = {
            **os.environ,
            "HERMES_HOME": str((REPOSITORY_ROOT / ".hermes-runtime").resolve()),
            "ATELIER_PROJECT_ROOT": str(REPOSITORY_ROOT),
            "HERMES_DASHBOARD_HOST": args.dashboard_host,
        }
        subprocess.Popen(
            [
                os.environ.get("HERMES_BIN", "hermes"),
                "-p",
                "default",
                "dashboard",
                "--host",
                args.dashboard_host,
                "--port",
                str(args.dashboard_port),
                "--no-open",
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            start_new_session=True,
        )
        print(f"dashboard starting at http://{args.dashboard_host}:{args.dashboard_port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

