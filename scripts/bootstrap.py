from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.paths import hermes_root  # noqa: E402
from plugin.atelier.services.apps import AppService  # noqa: E402
from plugin.atelier.services.profiles import ProfileService  # noqa: E402
from plugin.atelier.store import AtelierStore  # noqa: E402


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bootstrap the project-local Hermes Atelier")
    value.add_argument("--model", default=os.environ.get("ATELIER_MODEL"))
    value.add_argument("--base-url", default=os.environ.get("ATELIER_MODEL_BASE_URL"))
    value.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"))
    value.add_argument("--start", action="store_true", help="Start every installed Profile Gateway")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    missing = [
        name
        for name, configured in (
            ("--model / ATELIER_MODEL", args.model),
            ("--base-url / ATELIER_MODEL_BASE_URL", args.base_url),
            ("--api-key / OPENAI_API_KEY", args.api_key),
        )
        if not configured
    ]
    if missing:
        parser().error("missing runtime configuration: " + ", ".join(missing))
    root = hermes_root().resolve()
    if root != (REPOSITORY_ROOT / ".hermes-runtime").resolve():
        raise RuntimeError("refusing to bootstrap outside the repository-local Hermes root")
    store = AtelierStore()
    profiles = ProfileService(store)
    apps = AppService(store)
    profiles.bootstrap_root()
    model_env = {
        "OPENAI_API_KEY": args.api_key,
        "ATELIER_MODEL": args.model,
        "ATELIER_MODEL_BASE_URL": args.base_url.rstrip("/"),
    }
    installed: list[str] = []
    for name in ("atelier-builder", "atelier-reviewer"):
        profiles.install_distribution(REPOSITORY_ROOT / "profiles" / name, name)
        profiles.configure_runtime(name, app_id=None, model_env=model_env)
        installed.append(name)
    registered = apps.register_all()
    for app in registered:
        definition = apps.get_definition(app["id"])
        profiles.install_app(Path(app["source_path"]), definition, model_env=model_env)
        installed.extend(profile.name for profile in definition.profiles)
    if args.start:
        for profile in installed:
            profiles.start(profile)
    print(f"Hermes home: {root}")
    print(f"Installed Profiles: {', '.join(installed)}")
    print(f"Registered applications: {', '.join(app['id'] for app in registered) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

