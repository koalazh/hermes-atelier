from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path


def test_v2_wheel_contains_active_code_and_excludes_v1_state_machine(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    wheel = next(tmp_path.glob("hermes_atelier-2.1.0-*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    assert {
        "plugin/atelier/cli_v2.py",
        "plugin/atelier/dashboard/dist/index_v2.js",
        "plugin/profile_call/__init__.py",
    } <= names
    assert not {
        "plugin/atelier/cli.py",
        "plugin/atelier/models.py",
        "plugin/atelier/schemas.py",
        "plugin/atelier/store.py",
        "plugin/atelier/dashboard/plugin_api.py",
        "plugin/atelier/dashboard/dist/index.js",
        "plugin/atelier/services/apps.py",
    } & names
