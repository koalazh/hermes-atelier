from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LOGICAL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
PACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
FORBIDDEN_WORKFLOW_KEYS = {
    "steps",
    "workflow",
    "if",
    "else",
    "route_when",
    "parallel",
    "fan_out",
    "aggregate",
    "judge",
    "retry_policy_for_business",
}
RUNTIME_NAMES = {
    ".atelier",
    ".DS_Store",
    ".env",
    "__pycache__",
    "auth.json",
    "local",
    "memories",
    "memory",
    "sessions",
    "logs",
    "trace",
    "traces",
    "gateway.pid",
    "gateway_state.json",
    "processes.json",
}


class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distribution: str
    exposure: Literal["public", "internal"] = "internal"
    description: str | None = None

    @field_validator("distribution")
    @classmethod
    def relative_distribution(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path == Path("."):
            raise ValueError("distribution must be a non-empty relative path")
        return path.as_posix()


class PublicAPI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["openai"] = "openai"
    endpoints: list[Literal["/v1/responses", "/v1/chat/completions"]] = Field(min_length=1)
    output_contract: str | None = None


class AppManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    id: str
    version: str
    entry: str
    agents: dict[str, AgentDefinition]
    allowed_calls: dict[str, list[str]] = Field(default_factory=dict)
    collaboration: list[str] = Field(default_factory=list)
    public_api: PublicAPI
    state_policy: Literal["stateless", "session_only", "caller_scoped"]
    state_compatibility: Literal["preserve", "review_required", "reset_recommended"] = "preserve"
    cases: list[str] = Field(default_factory=list)
    contracts: list[str] = Field(default_factory=list)
    description: str | None = None

    @field_validator("id")
    @classmethod
    def valid_pack_id(cls, value: str) -> str:
        if len(value) < 2 or not PACK_ID_RE.fullmatch(value):
            raise ValueError("pack id must be lowercase kebab-case")
        return value

    @field_validator("entry")
    @classmethod
    def valid_entry(cls, value: str) -> str:
        if not LOGICAL_ID_RE.fullmatch(value):
            raise ValueError("invalid logical entry Agent ID")
        return value

    @field_validator("agents")
    @classmethod
    def valid_agents(cls, value: dict[str, AgentDefinition]) -> dict[str, AgentDefinition]:
        if not value:
            raise ValueError("at least one logical Agent is required")
        if any(not LOGICAL_ID_RE.fullmatch(agent_id) for agent_id in value):
            raise ValueError("invalid logical Agent ID")
        return value

    @model_validator(mode="after")
    def valid_graph(self) -> AppManifest:
        if self.entry not in self.agents:
            raise ValueError("entry must name a declared logical Agent")
        if self.agents[self.entry].exposure != "public":
            raise ValueError("entry Agent must be public")
        public = [name for name, agent in self.agents.items() if agent.exposure == "public"]
        if public != [self.entry]:
            raise ValueError("only the entry Agent may be public")
        for source, targets in self.allowed_calls.items():
            if source not in self.agents:
                raise ValueError(f"allowed_calls source is not declared: {source}")
            if len(targets) != len(set(targets)):
                raise ValueError(f"duplicate allowed_calls target for {source}")
            for target in targets:
                if target not in self.agents:
                    raise ValueError(f"allowed_calls target is not declared: {target}")
                if target == source:
                    raise ValueError("self calls are not allowed")
        return self


def _find_forbidden(value: Any, path: tuple[str, ...] = ()) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_WORKFLOW_KEYS:
                return ".".join((*path, key_text))
            found = _find_forbidden(item, (*path, key_text))
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_forbidden(item, (*path, str(index)))
            if found:
                return found
    return None


class AppPack:
    def __init__(self, root: Path, manifest: AppManifest) -> None:
        self.root = root.resolve()
        self.manifest = manifest

    @property
    def entry(self) -> str:
        return self.manifest.entry

    @classmethod
    def load(cls, root: Path) -> AppPack:
        root = root.resolve()
        manifest_path = root / "app.yaml"
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("app.yaml must contain a mapping")
        forbidden = _find_forbidden(raw)
        if forbidden:
            raise ValueError(f"workflow key is forbidden in app.yaml: {forbidden}")
        manifest = AppManifest.model_validate(raw)
        for agent_id, agent in manifest.agents.items():
            distribution = (root / agent.distribution).resolve()
            try:
                distribution.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"distribution escapes App Pack: {agent_id}") from exc
            if not (distribution / "distribution.yaml").is_file():
                raise ValueError(f"invalid Hermes Distribution for {agent_id}")
        for relative in [*manifest.cases, *manifest.contracts]:
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"App Pack resource escapes root: {relative}") from exc
            if not target.is_file():
                raise ValueError(f"missing App Pack resource: {relative}")
        return cls(root, manifest)

    def runtime_mapping(
        self,
        *,
        instance: str,
        agent_base_urls: dict[str, str],
        api_key_env: str,
        current_agent: str,
        trace: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not LOGICAL_ID_RE.fullmatch(instance) or current_agent not in self.manifest.agents:
            raise ValueError("invalid instance or current logical Agent")
        if set(agent_base_urls) != set(self.manifest.agents):
            raise ValueError("agent base URLs must cover every logical Agent")
        mapping: dict[str, Any] = {
            "schema_version": 1,
            "pack_id": self.manifest.id,
            "pack_version": self.manifest.version,
            "instance": instance,
            "current_agent": current_agent,
            "agents": {
                agent_id: {
                    "profile": f"{instance}--{agent_id}",
                    "base_url": agent_base_urls[agent_id].rstrip("/"),
                    "api_key_env": api_key_env,
                }
                for agent_id in self.manifest.agents
            },
            "allowed_calls": self.manifest.allowed_calls,
        }
        if trace:
            mapping["trace"] = trace
        return mapping


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_definition_snapshot(pack: AppPack) -> dict[str, Any]:
    agents: dict[str, Any] = {}
    digest = hashlib.sha256()
    manifest_bytes = (pack.root / "app.yaml").read_bytes()
    digest.update(b"app.yaml\0" + manifest_bytes)
    for agent_id, definition in sorted(pack.manifest.agents.items()):
        root = pack.root / definition.distribution
        files: dict[str, str] = {}
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            if any(part in RUNTIME_NAMES for part in path.relative_to(root).parts):
                continue
            value = _file_digest(path)
            files[relative] = value
            digest.update(agent_id.encode() + b"\0" + relative.encode() + b"\0" + value.encode())
        agents[agent_id] = {"distribution": definition.distribution, "files": files}
    return {
        "schema_version": 1,
        "pack_id": pack.manifest.id,
        "pack_version": pack.manifest.version,
        "revision": digest.hexdigest(),
        "agents": agents,
    }


def _ignore_runtime(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in RUNTIME_NAMES or name == "app.lock" or name.endswith((".pyc", ".pyo"))
    }


def release_pack(
    pack: AppPack,
    destination: Path,
    *,
    git_revision: str | None = None,
) -> dict[str, Any]:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(f"release destination already exists: {destination}")
    shutil.copytree(pack.root, destination, ignore=_ignore_runtime)
    if "profile_call" in pack.manifest.collaboration:
        plugin_source = Path(__file__).resolve().parents[1] / "profile_call"
        for source in pack.manifest.allowed_calls:
            distribution = destination / pack.manifest.agents[source].distribution
            plugin_target = distribution / "plugins" / "profile_call"
            plugin_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(plugin_source, plugin_target, ignore=_ignore_runtime)
            distribution_manifest_path = distribution / "distribution.yaml"
            distribution_manifest = (
                yaml.safe_load(distribution_manifest_path.read_text(encoding="utf-8")) or {}
            )
            owned = list(distribution_manifest.get("distribution_owned") or [])
            if "plugins/profile_call" not in owned:
                owned.append("plugins/profile_call")
            distribution_manifest["distribution_owned"] = owned
            distribution_manifest_path.write_text(
                yaml.safe_dump(distribution_manifest, sort_keys=False), encoding="utf-8"
            )
            config_path = distribution / "config.yaml"
            config = (
                yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if config_path.is_file()
                else {}
            )
            config = config if isinstance(config, dict) else {}
            plugins = config.setdefault("plugins", {})
            enabled = plugins.setdefault("enabled", [])
            enabled[:] = [item for item in enabled if item != "atelier"]
            if "profile_call" not in enabled:
                enabled.append("profile_call")
            config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    runner_source = Path(__file__).with_name("pack_app.py")
    shutil.copy2(runner_source, destination / "app")
    (destination / "app").chmod(0o755)
    released = AppPack.load(destination)
    snapshot = build_definition_snapshot(released)
    lock = {
        "schema_version": 1,
        "pack_id": released.manifest.id,
        "pack_version": released.manifest.version,
        "pack_revision": snapshot["revision"],
        "git_revision": git_revision,
        "agents": snapshot["agents"],
        "manifest": released.manifest.model_dump(mode="json"),
    }
    if released.manifest.cases:
        smoke = yaml.safe_load(
            (destination / released.manifest.cases[0]).read_text(encoding="utf-8")
        )
        if isinstance(smoke, dict) and isinstance(smoke.get("input"), str):
            lock["smoke_case"] = {
                "id": str(smoke.get("id") or Path(released.manifest.cases[0]).stem),
                "input": smoke["input"],
            }
    (destination / "app.lock").write_text(
        json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"path": str(destination), "revision": snapshot["revision"], "lock": lock}
