#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _env_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def _write_env(path: Path, updates: dict[str, str]) -> None:
    values = _env_values(path)
    values.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ["# Consumer-owned Hermes runtime configuration. Never commit this file."]
    body.extend(f"{key}={values[key]}" for key in sorted(values))
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(0o600)


class PackRuntime:
    def __init__(
        self,
        pack_root: Path,
        *,
        hermes_home: Path,
        hermes_bin: str = "hermes",
        hermes_runner: Callable[..., None] | None = None,
    ) -> None:
        self.pack_root = pack_root.resolve()
        self.hermes_home = hermes_home.resolve()
        self.hermes_bin = hermes_bin
        self.lock = _load_json(self.pack_root / "app.lock")
        self.hermes_runner = hermes_runner or self._run_hermes

    def _run_hermes(self, *args: str) -> None:
        subprocess.run(
            [self.hermes_bin, *args],
            cwd=self.pack_root,
            env={**os.environ, "HERMES_HOME": str(self.hermes_home)},
            check=True,
        )

    def _instance_state(self, instance: str) -> Path:
        return self.hermes_home / "app-packs" / instance

    def _physical(self, instance: str, agent_id: str) -> str:
        return f"{instance}--{agent_id}"

    def _install_agents(
        self,
        lock: dict[str, Any],
        pack_root: Path,
        *,
        instance: str,
    ) -> None:
        for agent_id, agent in lock["agents"].items():
            distribution = pack_root / agent["distribution"]
            self.hermes_runner(
                "-p",
                "default",
                "profile",
                "install",
                str(distribution),
                "--name",
                self._physical(instance, agent_id),
                "--yes",
                "--force",
            )

    def _write_install_state(self, *, instance: str) -> None:
        state = self._instance_state(instance)
        state.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.pack_root / "app.lock", state / "app.lock")
        (state / "install.json").write_text(
            json.dumps(
                {"pack_path": str(self.pack_root), "instance": instance},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def install(self, *, instance: str) -> None:
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        if not instance or any(character not in allowed for character in instance):
            raise ValueError("instance must contain only lowercase letters, digits, '-' or '_'")
        self.hermes_home.mkdir(parents=True, exist_ok=True)
        self._install_agents(self.lock, self.pack_root, instance=instance)
        self._write_install_state(instance=instance)

    def configure(
        self,
        *,
        instance: str,
        model: str,
        model_base_url: str,
        model_key_env: str,
        gateway_key_env: str,
        gateway_port: int,
    ) -> None:
        self._configure(
            self.lock,
            instance=instance,
            model=model,
            model_base_url=model_base_url,
            model_key_env=model_key_env,
            gateway_key_env=gateway_key_env,
            gateway_port=gateway_port,
        )

    def _configure(
        self,
        lock: dict[str, Any],
        *,
        instance: str,
        model: str,
        model_base_url: str,
        model_key_env: str,
        gateway_key_env: str,
        gateway_port: int,
    ) -> None:
        model_key = os.environ.get(model_key_env, "")
        gateway_key = os.environ.get(gateway_key_env, "")
        if not model or not model_base_url or not model_key:
            raise RuntimeError("model, model base URL, and model key environment are required")
        if len(gateway_key) < 16:
            raise RuntimeError("gateway API key must contain at least 16 characters")
        if not 1 <= gateway_port <= 65535:
            raise ValueError("gateway port is out of range")
        if gateway_port + len(lock["agents"]) - 1 > 65535:
            raise ValueError("gateway port range is out of range")

        manifest = lock["manifest"]
        agent_ports = {
            agent_id: gateway_port + index for index, agent_id in enumerate(lock["agents"])
        }
        for agent_id, agent_port in agent_ports.items():
            profile = self._physical(instance, agent_id)
            runtime = self.hermes_home / "profiles" / profile
            if not runtime.is_dir():
                raise RuntimeError(f"Profile is not installed: {profile}")
            self.hermes_runner("-p", profile, "config", "set", "model.default", model)
            self.hermes_runner("-p", profile, "config", "set", "model.provider", "custom:app_pack")
            self.hermes_runner(
                "-p",
                profile,
                "config",
                "set",
                "providers.app_pack.api",
                model_base_url.rstrip("/"),
                "--force",
            )
            self.hermes_runner(
                "-p",
                profile,
                "config",
                "set",
                "providers.app_pack.key_env",
                model_key_env,
                "--force",
            )
            _write_env(
                runtime / ".env",
                {
                    model_key_env: model_key,
                    gateway_key_env: gateway_key,
                    "API_SERVER_ENABLED": "true",
                    "API_SERVER_HOST": "127.0.0.1",
                    "API_SERVER_PORT": str(agent_port),
                    "API_SERVER_KEY": gateway_key,
                },
            )
            mapping = {
                "schema_version": 1,
                "pack_id": lock["pack_id"],
                "pack_version": lock["pack_version"],
                "instance": instance,
                "current_agent": agent_id,
                "agents": {
                    logical: {
                        "profile": self._physical(instance, logical),
                        "base_url": f"http://127.0.0.1:{agent_ports[logical]}",
                        "api_key_env": gateway_key_env,
                    }
                    for logical in lock["agents"]
                },
                "allowed_calls": manifest.get("allowed_calls", {}),
            }
            local = runtime / "local"
            local.mkdir(exist_ok=True)
            (local / "app-runtime.json").write_text(
                json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

        state = self._instance_state(instance)
        state.mkdir(parents=True, exist_ok=True)
        (state / "runtime.json").write_text(
            json.dumps(
                {
                    "entry_base_url": (f"http://127.0.0.1:{agent_ports[manifest['entry']]}"),
                    "gateway_key_env": gateway_key_env,
                    "gateway_base_port": gateway_port,
                    "agent_ports": agent_ports,
                    "model": model,
                    "model_base_url": model_base_url,
                    "model_key_env": model_key_env,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def _smoke(
        self,
        lock: dict[str, Any],
        *,
        instance: str,
        runtime: dict[str, Any],
    ) -> None:
        case = lock.get("smoke_case")
        if not isinstance(case, dict) or not isinstance(case.get("input"), str):
            return
        key_env = str(runtime["gateway_key_env"])
        entry = str(lock["manifest"]["entry"])
        key = _env_values(
            self.hermes_home / "profiles" / self._physical(instance, entry) / ".env"
        ).get(key_env, "")
        if not key:
            raise RuntimeError("smoke Case cannot resolve the Gateway API key")
        request = urllib.request.Request(
            f"{runtime['entry_base_url']}/v1/chat/completions",
            data=json.dumps(
                {
                    "model": self._physical(instance, entry),
                    "messages": [{"role": "user", "content": case["input"]}],
                }
            ).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Hermes-Session-Id": f"pack-update-smoke-{instance}",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for _ in range(15):
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    payload = json.loads(response.read())
                if payload.get("hermes", {}).get("failed") is True:
                    raise RuntimeError(str(payload["hermes"].get("error") or "smoke failed"))
                return
            except urllib.error.URLError as exc:
                last_error = exc
                time.sleep(1)
        raise RuntimeError(f"smoke Case failed: {last_error}")

    def _installed_lock(self, instance: str) -> dict[str, Any]:
        path = self._instance_state(instance) / "app.lock"
        if not path.is_file():
            raise RuntimeError(f"App Pack instance is not installed: {instance}")
        return _load_json(path)

    def _resolve_instance(self, instance: str | None) -> str:
        if instance:
            self._installed_lock(instance)
            return instance
        root = self.hermes_home / "app-packs"
        installed = (
            sorted(path.name for path in root.iterdir() if (path / "app.lock").is_file())
            if root.is_dir()
            else []
        )
        if len(installed) != 1:
            raise RuntimeError("--instance is required unless exactly one App Pack is installed")
        return installed[0]

    def gateway(
        self,
        action: str,
        *,
        instance: str | None = None,
        foreground: bool = False,
        force: bool = False,
    ) -> None:
        if action not in {"start", "stop", "restart", "status"}:
            raise ValueError(f"unsupported gateway action: {action}")
        resolved = self._resolve_instance(instance)
        lock = self._installed_lock(resolved)
        if foreground and len(lock["agents"]) != 1:
            raise RuntimeError("--foreground is only available for single-Agent App Packs")
        command = "run" if action == "start" and foreground else action
        for agent_id in lock["agents"]:
            args = ["-p", self._physical(resolved, agent_id), "gateway", command]
            if command == "run" and force:
                args.append("--force")
            self.hermes_runner(*args)

    def update(self, *, instance: str, restart: bool = True) -> None:
        state = self._instance_state(instance)
        old_lock_path = state / "app.lock"
        install_path = state / "install.json"
        if not old_lock_path.is_file() or not install_path.is_file():
            raise RuntimeError(f"App Pack instance is not installed: {instance}")
        old_lock = _load_json(old_lock_path)
        old_install = _load_json(install_path)
        old_pack = Path(str(old_install.get("pack_path") or "")).resolve()
        runtime_path = state / "runtime.json"
        runtime = _load_json(runtime_path) if runtime_path.is_file() else None
        old_agents = set(old_lock["agents"])
        new_agents = set(self.lock["agents"])
        if restart:
            self.gateway("stop", instance=instance)
        try:
            self._install_agents(self.lock, self.pack_root, instance=instance)
            for removed in sorted(old_agents - new_agents):
                self.hermes_runner(
                    "-p",
                    "default",
                    "profile",
                    "delete",
                    self._physical(instance, removed),
                    "--yes",
                )
            self._write_install_state(instance=instance)
            if runtime:
                self.configure(
                    instance=instance,
                    model=str(runtime["model"]),
                    model_base_url=str(runtime["model_base_url"]),
                    model_key_env=str(runtime["model_key_env"]),
                    gateway_key_env=str(runtime["gateway_key_env"]),
                    gateway_port=int(runtime["gateway_base_port"]),
                )
            if restart:
                self.gateway("start", instance=instance)
                if runtime:
                    refreshed = _load_json(runtime_path)
                    self._smoke(self.lock, instance=instance, runtime=refreshed)
        except Exception as exc:
            rollback_errors: list[str] = []
            try:
                if restart:
                    try:
                        self.gateway("stop", instance=instance)
                    except Exception:
                        pass
                self._install_agents(old_lock, old_pack, instance=instance)
                for added in sorted(new_agents - old_agents):
                    self.hermes_runner(
                        "-p",
                        "default",
                        "profile",
                        "delete",
                        self._physical(instance, added),
                        "--yes",
                    )
                shutil.copy2(old_pack / "app.lock", old_lock_path)
                install_path.write_text(
                    json.dumps(old_install, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                if runtime:
                    self._configure(
                        old_lock,
                        instance=instance,
                        model=str(runtime["model"]),
                        model_base_url=str(runtime["model_base_url"]),
                        model_key_env=str(runtime["model_key_env"]),
                        gateway_key_env=str(runtime["gateway_key_env"]),
                        gateway_port=int(runtime["gateway_base_port"]),
                    )
                if restart:
                    self.gateway("start", instance=instance)
                    if runtime:
                        restored = _load_json(runtime_path)
                        self._smoke(old_lock, instance=instance, runtime=restored)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
            detail = f"Pack update failed: {exc}"
            if rollback_errors:
                detail += f"; rollback incomplete: {'; '.join(rollback_errors)}"
            else:
                detail += "; previous distributions restored"
            raise RuntimeError(detail) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Thin Hermes App Pack lifecycle proxy")
    parser.add_argument("--hermes-home", type=Path, default=os.environ.get("HERMES_HOME"))
    parser.add_argument("--hermes-bin", default=os.environ.get("HERMES_BIN", "hermes"))
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install")
    install.add_argument("--instance", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--instance", required=True)
    configure.add_argument("--model", required=True)
    configure.add_argument("--model-base-url", required=True)
    configure.add_argument("--model-key-env", default="OPENAI_API_KEY")
    configure.add_argument("--gateway-key-env", default="HERMES_APP_API_KEY")
    configure.add_argument("--gateway-port", type=int, default=8080)
    start = commands.add_parser("start")
    start.add_argument("--instance")
    start.add_argument("--foreground", action="store_true")
    start.add_argument("--force", action="store_true")
    for action in ("stop", "restart", "status"):
        command = commands.add_parser(action)
        command.add_argument("--instance")
    update = commands.add_parser("update")
    update.add_argument("--instance", required=True)
    update.add_argument("--no-restart", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.hermes_home is None:
        raise SystemExit("--hermes-home or HERMES_HOME is required")
    runtime = PackRuntime(
        Path(__file__).resolve().parent,
        hermes_home=args.hermes_home,
        hermes_bin=args.hermes_bin,
    )
    if args.command == "install":
        runtime.install(instance=args.instance)
    elif args.command == "configure":
        runtime.configure(
            instance=args.instance,
            model=args.model,
            model_base_url=args.model_base_url,
            model_key_env=args.model_key_env,
            gateway_key_env=args.gateway_key_env,
            gateway_port=args.gateway_port,
        )
    elif args.command == "update":
        runtime.update(instance=args.instance, restart=not args.no_restart)
    else:
        runtime.gateway(
            args.command,
            instance=getattr(args, "instance", None),
            foreground=getattr(args, "foreground", False),
            force=getattr(args, "force", False),
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
