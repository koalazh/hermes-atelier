from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plugin.atelier.errors import AtelierError
from plugin.atelier.services.profiles import (
    ProfileService,
    _env_values,
    _materialize_terminal_cwd,
    _set_model_config,
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


def test_model_runtime_config_uses_env_reference_without_persisting_secret(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("plugins:\n  enabled: [atelier]\n", encoding="utf-8")
    secret = "runtime-secret-value"

    _set_model_config(
        config,
        {
            "ATELIER_MODEL": "example-model",
            "ATELIER_MODEL_BASE_URL": "https://models.example/v1/",
            "OPENAI_API_KEY": secret,
        },
    )

    text = config.read_text(encoding="utf-8")
    assert "default: example-model" in text
    assert "provider: custom:atelier" in text
    assert "base_url: https://models.example/v1" in text
    assert "key_env: OPENAI_API_KEY" in text
    assert secret not in text


def test_project_terminal_path_is_materialized_for_current_hermes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    config = tmp_path / "config.yaml"
    config.write_text(
        "terminal:\n  cwd: ${ATELIER_PROJECT_ROOT}/apps/sample\n", encoding="utf-8"
    )

    _materialize_terminal_cwd(config)

    assert f"cwd: {tmp_path.resolve()}/apps/sample" in config.read_text(encoding="utf-8")


def test_pid_ownership_requires_matching_profile_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ProfileService, "_pid_alive", staticmethod(lambda pid: True))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "python hermes -p another--profile gateway run\n", ""
        ),
    )

    assert not ProfileService._pid_owned("sample-app--entry", 1234)


def test_stop_does_not_signal_unowned_reused_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AtelierStore(tmp_path / "atelier.db")
    store.set_endpoint(
        profile="sample-app--entry",
        app_id=None,
        host="127.0.0.1",
        port=18100,
        status="healthy",
        pid=1234,
    )
    service = ProfileService(store)
    monkeypatch.setattr(service, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(service, "_pid_owned", lambda profile, pid: False)

    def unexpected_kill(pid: int, sig: int) -> None:
        raise AssertionError("an unowned PID must never be signalled")

    monkeypatch.setattr("plugin.atelier.services.profiles.os.kill", unexpected_kill)

    result = service.stop("sample-app--entry")

    assert result["status"] == "stopped"
    assert result["pid"] is None
    assert "stale PID" in result["last_error"]


def test_failed_start_terminates_the_spawned_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    store = AtelierStore(tmp_path / "atelier.db")
    store.set_endpoint(
        profile="sample-app--entry",
        app_id=None,
        host="127.0.0.1",
        port=18100,
    )
    service = ProfileService(store)

    class FakeProcess:
        pid = 4321
        terminated = False

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, *, timeout: float) -> int:
            return 0

        def poll(self) -> int | None:
            return 0 if self.terminated else None

    process = FakeProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)

    def fail_health(profile: str, *, timeout: float) -> None:
        raise AtelierError("profile_unhealthy", "health failed")

    monkeypatch.setattr(service, "wait_healthy", fail_health)

    with pytest.raises(AtelierError, match="health failed"):
        service.start("sample-app--entry")

    assert process.terminated
    endpoint = store.get_endpoint("sample-app--entry")
    assert endpoint["status"] == "unhealthy"  # type: ignore[index]
    assert endpoint["pid"] is None  # type: ignore[index]
