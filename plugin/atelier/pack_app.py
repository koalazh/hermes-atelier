#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _event_output(event: dict[str, Any]) -> str:
    output = event.get("output")
    if isinstance(output, str):
        return output
    response = event.get("response")
    if isinstance(response, dict):
        nested = response.get("output_text") or response.get("output")
        if isinstance(nested, str):
            return nested
    return ""


def _json_schema_errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if isinstance(expected, str) and not matches.get(expected, False):
        return [f"{path} must be {expected}"]
    if isinstance(value, dict):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for required in schema.get("required") or []:
            if required not in value:
                errors.append(f"{path}.{required} is required")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key} is not allowed")
        for key, child in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, dict):
                errors.extend(_json_schema_errors(child, child_schema, f"{path}.{key}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, child in enumerate(value):
            errors.extend(_json_schema_errors(child, schema["items"], f"{path}[{index}]"))
    return errors


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
        entry = str(manifest["entry"])
        ordered_agents = [entry, *(agent_id for agent_id in lock["agents"] if agent_id != entry)]
        agent_ports = {
            agent_id: gateway_port + index for index, agent_id in enumerate(ordered_agents)
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
                "pack_revision": lock["pack_revision"],
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

        runtime_definition: dict[str, dict[str, str]] = {}
        for agent_id, agent in lock["agents"].items():
            profile_root = self.hermes_home / "profiles" / self._physical(instance, agent_id)
            files: dict[str, str] = {}
            for relative in agent["files"]:
                path = profile_root / relative
                if not path.is_file() or path.is_symlink():
                    raise RuntimeError(f"installed Profile asset is missing: {agent_id}/{relative}")
                files[relative] = _digest(path)
            runtime_definition[agent_id] = files

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
                    "runtime_definition": runtime_definition,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def _gateway_key(
        self,
        lock: dict[str, Any],
        *,
        instance: str,
        runtime: dict[str, Any],
    ) -> str:
        key_env = str(runtime["gateway_key_env"])
        entry = str(lock["manifest"]["entry"])
        key = _env_values(
            self.hermes_home / "profiles" / self._physical(instance, entry) / ".env"
        ).get(key_env, "")
        if not key:
            raise RuntimeError("Case runner cannot resolve the Gateway API key")
        return key

    @staticmethod
    def _wait_for_gateway(base_url: str, key: str) -> None:
        last_error: Exception | None = None
        request = urllib.request.Request(
            f"{base_url}/health",
            headers={"Authorization": f"Bearer {key}"},
        )
        for _ in range(15):
            try:
                with urllib.request.urlopen(request, timeout=5):
                    return
            except urllib.error.URLError as exc:
                last_error = exc
                time.sleep(1)
        raise RuntimeError(f"entry Gateway is unavailable: {last_error}")

    def _entry_run(
        self,
        *,
        lock: dict[str, Any],
        instance: str,
        runtime: dict[str, Any],
        case: dict[str, Any],
        session_id: str,
    ) -> tuple[str, str, str]:
        key = self._gateway_key(lock, instance=instance, runtime=runtime)
        base_url = str(runtime["entry_base_url"]).rstrip("/")
        self._wait_for_gateway(base_url, key)
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if case.get("memory_policy") == "retained":
            scope = str(case.get("memory_scope") or "")
            if not scope:
                raise RuntimeError("retained Case requires memory_scope")
            headers["X-Hermes-Session-Key"] = scope
        request = urllib.request.Request(
            f"{base_url}/v1/runs",
            data=json.dumps({"input": case["input"], "session_id": session_id}).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            created = json.loads(response.read())
        run_id = str(created.get("run_id") or "")
        if not run_id:
            raise RuntimeError("Hermes did not return a Run ID")

        output_parts: list[str] = []
        terminal: dict[str, Any] | None = None
        events = urllib.request.Request(
            f"{base_url}/v1/runs/{run_id}/events",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(events, timeout=900) as response:
            for raw_line in response:
                line = raw_line.decode(errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                raw = line.removeprefix("data:").strip()
                if not raw:
                    continue
                event = json.loads(raw)
                if event.get("event") == "message.delta" and isinstance(
                    event.get("delta"), str
                ):
                    output_parts.append(event["delta"])
                if str(event.get("event") or "").startswith("run."):
                    terminal = event
        if terminal is None:
            status_request = urllib.request.Request(
                f"{base_url}/v1/runs/{run_id}",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(status_request, timeout=30) as response:
                terminal = json.loads(response.read())
        status = str(terminal.get("status") or terminal.get("event", "")).removeprefix("run.")
        output = _event_output(terminal) or "".join(output_parts)
        return run_id, status, output

    def _case_trace_paths(self, lock: dict[str, Any], instance: str) -> dict[Path, bytes]:
        backups: dict[Path, bytes] = {}
        for agent_id in lock["agents"]:
            path = (
                self.hermes_home
                / "profiles"
                / self._physical(instance, agent_id)
                / "local"
                / "app-runtime.json"
            )
            if not path.is_file():
                raise RuntimeError(f"runtime mapping is missing for {agent_id}")
            backups[path] = path.read_bytes()
        return backups

    @staticmethod
    def _restore_trace_paths(backups: dict[Path, bytes]) -> None:
        for path, content in backups.items():
            path.write_bytes(content)

    @staticmethod
    def _read_traces(path: Path, session_id: str) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        traces = []
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if isinstance(value, dict) and value.get("source_session_id") == session_id:
                traces.append(value)
        return traces

    @staticmethod
    def _assertions(
        case: dict[str, Any], *, output: str, traces: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        assertions = case.get("assertions") if isinstance(case.get("assertions"), dict) else {}
        calls = assertions.get("calls") if isinstance(assertions.get("calls"), dict) else {}
        output_rules = (
            assertions.get("output") if isinstance(assertions.get("output"), dict) else {}
        )
        completed = {
            str(event.get("target"))
            for event in traces
            if event.get("event") == "profile_call.completed"
        }
        attempted = {str(event.get("target")) for event in traces}
        results = [
            {"kind": "calls.required", "value": target, "passed": target in completed}
            for target in calls.get("required") or []
        ]
        results.extend(
            {"kind": "calls.forbidden", "value": target, "passed": target not in attempted}
            for target in calls.get("forbidden") or []
        )
        folded = output.casefold()
        results.extend(
            {
                "kind": "output.must_contain",
                "value": value,
                "passed": str(value).casefold() in folded,
            }
            for value in output_rules.get("must_contain") or []
        )
        results.extend(
            {
                "kind": "output.must_not_claim",
                "value": value,
                "passed": str(value).casefold() not in folded,
            }
            for value in output_rules.get("must_not_claim") or []
        )
        return results

    def _contract_assertion(self, lock: dict[str, Any], output: str) -> dict[str, Any] | None:
        relative = lock["manifest"].get("public_api", {}).get("output_contract")
        if not relative:
            return None
        contract_path = self.pack_root / str(relative)
        try:
            value = json.loads(output)
            schema = _load_json(contract_path)
            errors = _json_schema_errors(value, schema)
        except (json.JSONDecodeError, OSError, RuntimeError) as exc:
            errors = [str(exc)]
        return {
            "kind": "contract.output",
            "value": str(relative),
            "passed": not errors,
            "errors": errors[:20],
        }

    def _run_case(
        self,
        lock: dict[str, Any],
        *,
        instance: str,
        runtime: dict[str, Any],
        case: dict[str, Any],
    ) -> dict[str, Any]:
        relative = str(case.get("path") or "")
        case_path = self.pack_root / relative
        if not case_path.is_file() or _digest(case_path) != case.get("hash"):
            raise RuntimeError(f"Case does not match app.lock: {relative}")
        run_nonce = uuid.uuid4().hex
        session_id = f"pack_case_{str(case.get('id') or 'case')}_{run_nonce}"
        trace_path = self._instance_state(instance) / "case-runs" / f"{run_nonce}.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        backups = self._case_trace_paths(lock, instance)
        try:
            for path in backups:
                mapping = _load_json(path)
                mapping["trace"] = {"file": str(trace_path)}
                path.write_text(
                    json.dumps(mapping, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            run_id, status, output = self._entry_run(
                lock=lock,
                instance=instance,
                runtime=runtime,
                case=case,
                session_id=session_id,
            )
            traces = self._read_traces(trace_path, session_id)
        finally:
            self._restore_trace_paths(backups)
            trace_path.unlink(missing_ok=True)
        assertions = self._assertions(case, output=output, traces=traces)
        contract = self._contract_assertion(lock, output)
        if contract:
            assertions.append(contract)
        return {
            "id": case.get("id"),
            "session_id": session_id,
            "hermes_run_id": run_id,
            "status": status,
            "output": output,
            "traces": traces,
            "assertions": assertions,
            "passed": status == "completed" and all(item["passed"] for item in assertions),
        }

    def run_cases(self, *, instance: str, case_id: str | None = None) -> dict[str, Any]:
        lock = self._installed_lock(instance)
        install = _load_json(self._instance_state(instance) / "install.json")
        installed_pack = Path(str(install.get("pack_path") or "")).resolve()
        if installed_pack != self.pack_root:
            raise RuntimeError("run Cases with the wrapper from the installed App Pack")
        runtime = _load_json(self._instance_state(instance) / "runtime.json")
        cases = [
            case
            for case in lock.get("cases") or []
            if not case_id or case.get("id") == case_id
        ]
        if not cases:
            raise RuntimeError(f"unknown or missing Case: {case_id or '<all>'}")
        results = [
            self._run_case(lock, instance=instance, runtime=runtime, case=case) for case in cases
        ]
        return {
            "instance": instance,
            "passed": all(item["passed"] for item in results),
            "cases": results,
        }

    def _smoke(
        self,
        lock: dict[str, Any],
        *,
        instance: str,
        runtime: dict[str, Any],
        pack_root: Path,
    ) -> None:
        cases = lock.get("cases") or []
        if not cases:
            return
        original_root = self.pack_root
        try:
            self.pack_root = pack_root.resolve()
            result = self._run_case(
                lock,
                instance=instance,
                runtime=runtime,
                case=cases[0],
            )
        finally:
            self.pack_root = original_root
        if not result["passed"]:
            raise RuntimeError(f"smoke Case failed: {result['id']}")

    def _installed_lock(self, instance: str) -> dict[str, Any]:
        path = self._instance_state(instance) / "app.lock"
        if not path.is_file():
            raise RuntimeError(f"App Pack instance is not installed: {instance}")
        return _load_json(path)

    def attest(self, *, instance: str) -> dict[str, Any]:
        lock = self._installed_lock(instance)
        state = self._instance_state(instance)
        install = _load_json(state / "install.json")
        runtime = _load_json(state / "runtime.json")
        installed_pack = Path(str(install.get("pack_path") or "")).resolve()
        if installed_pack != self.pack_root:
            raise RuntimeError("attestation wrapper does not match the installed App Pack")

        digest = hashlib.sha256()
        for relative, expected in sorted(lock.get("files", {}).items()):
            path = (self.pack_root / relative).resolve()
            try:
                path.relative_to(self.pack_root)
            except ValueError as exc:
                raise RuntimeError(f"release asset escapes App Pack: {relative}") from exc
            if path.is_symlink() or not path.is_file() or _digest(path) != expected:
                raise RuntimeError(f"release asset does not match app.lock: {relative}")
            digest.update(relative.encode() + b"\0" + expected.encode())
        if digest.hexdigest() != lock.get("pack_revision"):
            raise RuntimeError("app.lock Pack revision is inconsistent")

        recorded_definition = runtime.get("runtime_definition")
        if not isinstance(recorded_definition, dict):
            raise RuntimeError("runtime definition attestation is missing")
        if set(recorded_definition) != set(lock["agents"]):
            raise RuntimeError("runtime definition does not cover every logical Agent")
        for agent_id, expected_files in recorded_definition.items():
            if agent_id not in lock["agents"] or not isinstance(expected_files, dict):
                raise RuntimeError("runtime definition attestation is invalid")
            profile_root = self.hermes_home / "profiles" / self._physical(instance, agent_id)
            for relative, expected in expected_files.items():
                path = (profile_root / relative).resolve()
                try:
                    path.relative_to(profile_root.resolve())
                except ValueError as exc:
                    raise RuntimeError(
                        f"installed Profile asset escapes root: {agent_id}/{relative}"
                    ) from exc
                if path.is_symlink() or not path.is_file() or _digest(path) != expected:
                    raise RuntimeError(
                        f"installed Profile asset changed: {agent_id}/{relative}"
                    )
            mapping = _load_json(profile_root / "local" / "app-runtime.json")
            if (
                mapping.get("pack_revision") != lock["pack_revision"]
                or mapping.get("current_agent") != agent_id
            ):
                raise RuntimeError(f"runtime mapping does not match app.lock: {agent_id}")

        return {
            "verified": True,
            "instance": instance,
            "pack_id": lock["pack_id"],
            "pack_version": lock["pack_version"],
            "pack_revision": lock["pack_revision"],
            "source_revision": lock["source_revision"],
            "source_provenance": lock["source_provenance"],
            "definition_snapshot": lock["definition_snapshot"],
            "cases": lock.get("cases") or [],
            "model_fingerprint": {
                "provider": "custom:app_pack",
                "model": runtime["model"],
                "base_url": runtime["model_base_url"],
            },
            "entry_base_url": runtime["entry_base_url"],
            "gateway_key_env": runtime["gateway_key_env"],
        }

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
                    self._smoke(
                        self.lock,
                        instance=instance,
                        runtime=refreshed,
                        pack_root=self.pack_root,
                    )
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
                        self._smoke(
                            old_lock,
                            instance=instance,
                            runtime=restored,
                            pack_root=old_pack,
                        )
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
    cases = commands.add_parser("cases")
    cases.add_argument("--instance", required=True)
    cases.add_argument("--case")
    attest = commands.add_parser("attest")
    attest.add_argument("--instance", required=True)
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
    elif args.command == "cases":
        result = runtime.run_cases(instance=args.instance, case_id=args.case)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["passed"] else 1
    elif args.command == "attest":
        print(json.dumps(runtime.attest(instance=args.instance), indent=2, ensure_ascii=False))
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
