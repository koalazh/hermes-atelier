from __future__ import annotations

from pathlib import Path

import pytest

from plugin.atelier.errors import AtelierError
from plugin.atelier.services.profiles import (
    ProfileService,
    _env_values,
    _set_terminal_cwd,
    _write_env,
)
from plugin.atelier.store import AtelierStore


def test_write_env_preserves_existing_and_uses_private_mode(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    _write_env(path, {"EXISTING": "one", "API_SERVER_KEY": "first-secret-value"})
    _write_env(path, {"API_SERVER_PORT": "18100"})

    values = _env_values(path)
    assert values == {
        "API_SERVER_KEY": "first-secret-value",
        "API_SERVER_PORT": "18100",
        "EXISTING": "one",
    }
    assert path.stat().st_mode & 0o777 == 0o600


def test_allocated_ports_are_distinct(tmp_path: Path) -> None:
    store = AtelierStore(tmp_path / "atelier.db")
    service = ProfileService(store)
    first = service.allocate_port()
    store.set_endpoint(profile="one--entry", app_id=None, host="127.0.0.1", port=first)
    second = service.allocate_port()

    assert first != second


def test_endpoint_credentials_fail_without_runtime_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / ".hermes-runtime"
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store = AtelierStore(tmp_path / "atelier.db")
    store.set_endpoint(profile="one--entry", app_id=None, host="127.0.0.1", port=18100)
    (root / "profiles" / "one--entry").mkdir(parents=True)
    service = ProfileService(store)

    with pytest.raises(AtelierError, match="missing API key"):
        service.endpoint_credentials("one--entry")


def test_terminal_cwd_is_written_as_an_absolute_profile_setting(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("terminal:\n  backend: local\n", encoding="utf-8")
    workdir = tmp_path / "draft"
    workdir.mkdir()

    _set_terminal_cwd(config, workdir)

    assert f"cwd: {workdir.resolve()}" in config.read_text(encoding="utf-8")
