from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.hermes_http import HermesHTTPClient  # noqa: E402
from plugin.atelier.paths import hermes_root, profile_runtime_dir  # noqa: E402
from plugin.atelier.services.apps import AppService  # noqa: E402
from plugin.atelier.services.profiles import LOOPBACK, ProfileService  # noqa: E402
from plugin.atelier.store import AtelierStore  # noqa: E402


async def check(*, include_health: bool) -> dict:
    expected_root = (REPOSITORY_ROOT / ".hermes-runtime").resolve()
    if hermes_root().resolve() != expected_root:
        raise RuntimeError("HERMES_HOME is not the repository-local runtime")
    store = AtelierStore()
    apps = AppService(store)
    profiles = ProfileService(store)
    registered = apps.register_all()
    endpoints = store.list_endpoints()
    expected_profiles = {
        "atelier-builder",
        "atelier-reviewer",
        *(
            profile.name
            for app in registered
            for profile in apps.get_definition(app["id"]).profiles
        ),
    }
    if {item["profile"] for item in endpoints} != expected_profiles:
        raise RuntimeError("registered endpoints do not match versioned Profiles")
    checked = []
    for endpoint in endpoints:
        if endpoint["host"] != LOOPBACK:
            raise RuntimeError(f"non-loopback endpoint: {endpoint['profile']}")
        runtime = profile_runtime_dir(endpoint["profile"])
        env_path = runtime / ".env"
        if not (runtime / "distribution.yaml").is_file() or not env_path.is_file():
            raise RuntimeError(f"incomplete runtime Profile: {endpoint['profile']}")
        if env_path.stat().st_mode & 0o077:
            raise RuntimeError(f"runtime .env is not private: {endpoint['profile']}")
        if include_health:
            base_url, key = profiles.endpoint_credentials(endpoint["profile"])
            await HermesHTTPClient(base_url, key).health()
        checked.append(endpoint["profile"])
    version = subprocess.run(
        [os.environ.get("HERMES_BIN", "hermes"), "--version"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "HERMES_HOME": str(expected_root)},
    ).stdout.strip()
    return {
        "hermes": version,
        "hermes_home": str(expected_root),
        "applications": [app["id"] for app in registered],
        "profiles": checked,
        "health_checked": include_health,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the installed Hermes capability boundary")
    parser.add_argument("--skip-health", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(check(include_health=not args.skip_health)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
