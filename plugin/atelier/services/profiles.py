from __future__ import annotations

import os
import secrets
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from ..errors import AtelierError
from ..paths import atelier_root, hermes_root, profile_runtime_dir, project_root
from ..schemas import AppDefinition
from ..store import AtelierStore

LOOPBACK = "127.0.0.1"
PORT_START = 18100
PORT_END = 18999


def _env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(path: Path, updates: dict[str, str]) -> None:
    existing = _env_values(path)
    existing.update({key: str(value) for key, value in updates.items() if value is not None})
    lines = ["# Runtime-only Hermes Profile configuration. Never commit this file."]
    lines.extend(f"{key}={existing[key]}" for key in sorted(existing))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _set_plugin_enabled(config_path: Path) -> None:
    config: dict[str, Any] = {}
    if config_path.is_file():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            config = loaded
    plugins = config.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise ValueError(f"plugins configuration must be a mapping: {config_path}")
    enabled = plugins.setdefault("enabled", [])
    if not isinstance(enabled, list):
        raise ValueError(f"plugins.enabled must be a list: {config_path}")
    if "atelier" not in enabled:
        enabled.append("atelier")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def _install_plugin_link(home: Path) -> None:
    source = project_root() / "plugin" / "atelier"
    destination = home / "plugins" / "atelier"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() == source.resolve():
            return
        destination.unlink()
    elif destination.exists():
        shutil.rmtree(destination)
    try:
        destination.symlink_to(source, target_is_directory=True)
    except OSError:
        shutil.copytree(source, destination)


class ProfileService:
    def __init__(self, store: AtelierStore, *, hermes_bin: str | None = None) -> None:
        self.store = store
        self.hermes_bin = hermes_bin or os.environ.get("HERMES_BIN", "hermes")

    @property
    def subprocess_env(self) -> dict[str, str]:
        return {
            **os.environ,
            "HERMES_HOME": str(hermes_root().resolve()),
            "ATELIER_PROJECT_ROOT": str(project_root()),
        }

    def bootstrap_root(self) -> None:
        root = hermes_root()
        root.mkdir(parents=True, exist_ok=True)
        (root / "profiles").mkdir(exist_ok=True)
        _install_plugin_link(root)
        _set_plugin_enabled(root / "config.yaml")

    def allocate_port(self) -> int:
        used = {int(item["port"]) for item in self.store.list_endpoints()}
        for port in range(PORT_START, PORT_END + 1):
            if port in used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind((LOOPBACK, port))
                except OSError:
                    continue
            return port
        raise AtelierError("profile_install_failed", "no local development ports available")

    def install_distribution(self, source: Path, profile: str) -> Path:
        self.bootstrap_root()
        source = source.resolve()
        if not (source / "distribution.yaml").is_file():
            raise AtelierError("profile_install_failed", f"missing distribution.yaml for {profile}")
        runtime = profile_runtime_dir(profile)
        if runtime.exists() and (runtime / "distribution.yaml").is_file():
            command = [
                self.hermes_bin,
                "-p",
                "default",
                "profile",
                "update",
                profile,
                "--yes",
                "--force-config",
            ]
        else:
            command = [
                self.hermes_bin,
                "-p",
                "default",
                "profile",
                "install",
                str(source),
                "--name",
                profile,
                "--yes",
                "--force",
            ]
        result = subprocess.run(
            command,
            cwd=project_root(),
            env=self.subprocess_env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "profile install failed").strip()
            raise AtelierError(
                "profile_install_failed",
                f"Hermes failed to install {profile}: {message[-2000:]}",
            )
        _install_plugin_link(runtime)
        _set_plugin_enabled(runtime / "config.yaml")
        return runtime

    def configure_runtime(
        self,
        profile: str,
        *,
        app_id: str | None,
        model_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        runtime = profile_runtime_dir(profile)
        if not runtime.is_dir():
            raise AtelierError("profile_install_failed", f"profile is not installed: {profile}")
        existing_endpoint = self.store.get_endpoint(profile)
        port = int(existing_endpoint["port"]) if existing_endpoint else self.allocate_port()
        current = _env_values(runtime / ".env")
        api_key = current.get("API_SERVER_KEY") or secrets.token_urlsafe(32)
        updates = {
            "API_SERVER_ENABLED": "true",
            "API_SERVER_HOST": LOOPBACK,
            "API_SERVER_PORT": str(port),
            "API_SERVER_KEY": api_key,
            "ATELIER_PROJECT_ROOT": str(project_root()),
        }
        if model_env:
            updates.update({key: value for key, value in model_env.items() if value})
        _write_env(runtime / ".env", updates)
        status = existing_endpoint["status"] if existing_endpoint else "stopped"
        pid = existing_endpoint.get("pid") if existing_endpoint else None
        return self.store.set_endpoint(
            profile=profile,
            app_id=app_id,
            host=LOOPBACK,
            port=port,
            status=status,
            pid=pid,
        )

    def model_environment(self, profile: str) -> dict[str, str]:
        values = _env_values(profile_runtime_dir(profile) / ".env")
        allowed = {
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "LLM_API_KEY",
            "LLM_BASE_URL",
            "LLM_MODEL",
            "LLM_PROVIDER",
        }
        return {key: value for key, value in values.items() if key in allowed and value}

    def install_app(
        self,
        app_dir: Path,
        definition: AppDefinition,
        *,
        model_env: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        endpoints = []
        for profile in definition.profiles:
            self.install_distribution(app_dir / profile.source, profile.name)
            endpoints.append(
                self.configure_runtime(profile.name, app_id=definition.id, model_env=model_env)
            )
        return endpoints

    def endpoint_credentials(self, profile: str) -> tuple[str, str]:
        endpoint = self.store.get_endpoint(profile)
        if endpoint is None:
            raise AtelierError("endpoint_unavailable", f"no endpoint registered for {profile}")
        if endpoint["host"] != LOOPBACK:
            raise AtelierError("endpoint_unavailable", "non-loopback Profile endpoint rejected")
        values = _env_values(profile_runtime_dir(profile) / ".env")
        key = values.get("API_SERVER_KEY", "")
        if len(key) < 16:
            raise AtelierError("endpoint_unavailable", f"missing API key for {profile}")
        if values.get("API_SERVER_HOST") != LOOPBACK:
            raise AtelierError("endpoint_unavailable", "runtime Profile host is not loopback")
        if int(values.get("API_SERVER_PORT", "0")) != int(endpoint["port"]):
            raise AtelierError(
                "endpoint_unavailable", "runtime Profile port does not match registry"
            )
        return f"http://{LOOPBACK}:{endpoint['port']}", key

    def start(self, profile: str, *, terminal_cwd: Path | None = None) -> dict[str, Any]:
        endpoint = self.store.get_endpoint(profile)
        if endpoint is None:
            raise AtelierError("profile_install_failed", f"profile is not configured: {profile}")
        if endpoint["status"] in {"starting", "healthy"} and self._pid_alive(endpoint.get("pid")):
            return endpoint
        logs = atelier_root() / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        log_path = logs / f"{profile}.log"
        environment = self.subprocess_env
        if terminal_cwd is not None:
            environment["TERMINAL_CWD"] = str(terminal_cwd.resolve())
        with log_path.open("ab") as output:
            process = subprocess.Popen(
                [self.hermes_bin, "-p", profile, "gateway", "run"],
                cwd=terminal_cwd or project_root(),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.store.update_endpoint_status(profile, "starting", pid=process.pid)
        try:
            self.wait_healthy(profile, timeout=30)
        except Exception as exc:
            self.store.update_endpoint_status(
                profile, "unhealthy", pid=process.pid, last_error=str(exc)[:2000]
            )
            raise
        self.store.update_endpoint_status(profile, "healthy", pid=process.pid)
        return self.store.get_endpoint(profile)  # type: ignore[return-value]

    def wait_healthy(self, profile: str, *, timeout: float) -> None:
        base_url, api_key = self.endpoint_credentials(profile)
        deadline = time.monotonic() + timeout
        last_error = "not reachable"
        while time.monotonic() < deadline:
            try:
                response = httpx.get(
                    f"{base_url}/health",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=1,
                )
                if response.status_code == 200:
                    return
                last_error = f"health returned {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(0.25)
        raise AtelierError("profile_unhealthy", f"{profile} did not become healthy: {last_error}")

    def stop(self, profile: str, *, timeout: float = 15) -> dict[str, Any]:
        endpoint = self.store.get_endpoint(profile)
        if endpoint is None:
            raise AtelierError("endpoint_unavailable", f"unknown Profile endpoint: {profile}")
        pid = endpoint.get("pid")
        if not self._pid_alive(pid):
            self.store.update_endpoint_status(profile, "stopped", pid=None)
            return self.store.get_endpoint(profile)  # type: ignore[return-value]
        self.store.update_endpoint_status(profile, "stopping", pid=pid)
        os.kill(int(pid), signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and self._pid_alive(pid):
            time.sleep(0.1)
        if self._pid_alive(pid):
            self.store.update_endpoint_status(
                profile, "unhealthy", pid=pid, last_error="gateway did not stop after SIGTERM"
            )
            raise AtelierError("profile_unhealthy", f"{profile} did not stop")
        self.store.update_endpoint_status(profile, "stopped", pid=None)
        return self.store.get_endpoint(profile)  # type: ignore[return-value]

    def restart(self, profile: str, *, terminal_cwd: Path | None = None) -> dict[str, Any]:
        self.stop(profile)
        return self.start(profile, terminal_cwd=terminal_cwd)

    def status(self, profile: str) -> dict[str, Any]:
        endpoint = self.store.get_endpoint(profile)
        if endpoint is None:
            raise AtelierError("endpoint_unavailable", f"unknown Profile endpoint: {profile}")
        value = dict(endpoint)
        if value["status"] in {"starting", "healthy", "stopping"} and not self._pid_alive(
            value.get("pid")
        ):
            self.store.update_endpoint_status(profile, "stopped", pid=None)
            value = self.store.get_endpoint(profile)  # type: ignore[assignment]
        value["endpoint"] = f"http://{LOOPBACK}:{value['port']}"
        return value

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, ValueError):
            return False
