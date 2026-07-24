from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    configured = os.environ.get("ATELIER_PROJECT_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2]
    return root.resolve()


def hermes_root() -> Path:
    return project_root() / ".hermes-runtime"


def atelier_root() -> Path:
    return project_root() / ".atelier"


def database_path() -> Path:
    return atelier_root() / "atelier.db"


def apps_root() -> Path:
    return project_root() / "apps"


def drafts_root() -> Path:
    return apps_root() / ".drafts"


def ensure_within(path: Path, root: Path, *, allow_root: bool = False) -> Path:
    resolved = path.resolve()
    safe_root = root.resolve()
    try:
        relative = resolved.relative_to(safe_root)
    except ValueError as exc:
        raise ValueError(f"path escapes allowed root: {resolved}") from exc
    if not allow_root and relative == Path("."):
        raise ValueError(f"path must be below allowed root: {safe_root}")
    return resolved


def profile_runtime_dir(profile: str) -> Path:
    return hermes_root() / "profiles" / profile
