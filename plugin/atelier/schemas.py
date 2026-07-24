from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

APP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
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


class ProfileDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not PROFILE_RE.fullmatch(value):
            raise ValueError("invalid Hermes profile name")
        return value

    @field_validator("source")
    @classmethod
    def relative_source(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path == Path("."):
            raise ValueError("profile source must be a non-empty relative path")
        return path.as_posix()


class AppDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: str
    display_name: str = Field(min_length=1, max_length=100)
    entry_profile: str
    profiles: list[ProfileDefinition] = Field(min_length=1)
    allowed_calls: dict[str, list[str]] = Field(default_factory=dict)
    scenarios_dir: str = "scenarios"
    description: str | None = None

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if len(value) < 2 or not APP_ID_RE.fullmatch(value):
            raise ValueError("app id must be lowercase kebab-case")
        return value

    @field_validator("entry_profile")
    @classmethod
    def valid_entry_profile(cls, value: str) -> str:
        if not PROFILE_RE.fullmatch(value):
            raise ValueError("invalid entry profile")
        return value

    @field_validator("scenarios_dir")
    @classmethod
    def relative_scenarios(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path == Path("."):
            raise ValueError("scenarios_dir must be a non-empty relative path")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_profile_graph(self) -> AppDefinition:
        names = [profile.name for profile in self.profiles]
        if len(names) != len(set(names)):
            raise ValueError("profile names must be unique")
        if self.entry_profile not in names:
            raise ValueError("entry_profile must name a declared profile")
        prefix = f"{self.id}--"
        if any(not name.startswith(prefix) for name in names):
            raise ValueError(f"all application profiles must start with {prefix!r}")
        known = set(names)
        for source, targets in self.allowed_calls.items():
            if source not in known:
                raise ValueError(f"allowed_calls source is not declared: {source}")
            if len(targets) != len(set(targets)):
                raise ValueError(f"duplicate allowed_calls target for {source}")
            for target in targets:
                if target not in known:
                    raise ValueError(f"allowed_calls target is not declared: {target}")
                if target == source:
                    raise ValueError("self calls are not allowed")
        return self

    def allows(self, source: str, target: str) -> bool:
        return target in self.allowed_calls.get(source, [])


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


def load_app_definition(path: Path) -> AppDefinition:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("app.yaml must contain a mapping")
    forbidden = _find_forbidden(raw)
    if forbidden:
        raise ValueError(f"workflow key is forbidden in app.yaml: {forbidden}")
    definition = AppDefinition.model_validate(raw)
    app_root = path.parent.resolve()
    for profile in definition.profiles:
        source = (app_root / profile.source).resolve()
        try:
            source.relative_to(app_root)
        except ValueError as exc:
            raise ValueError(
                f"profile source escapes application directory: {profile.source}"
            ) from exc
        if not source.is_dir():
            raise ValueError(f"profile source does not exist: {profile.source}")
        if not (source / "distribution.yaml").is_file():
            raise ValueError(f"profile source is not a Hermes Distribution: {profile.source}")
    scenarios = (app_root / definition.scenarios_dir).resolve()
    try:
        scenarios.relative_to(app_root)
    except ValueError as exc:
        raise ValueError("scenarios_dir escapes application directory") from exc
    if not scenarios.is_dir():
        raise ValueError(f"scenarios directory does not exist: {definition.scenarios_dir}")
    return definition


class AtelierCallInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    task: str = Field(min_length=1, max_length=50_000)
    memory_scope: str | None = Field(default=None, max_length=256)
    timeout_seconds: int = Field(default=120, ge=1, le=900)

    @field_validator("target")
    @classmethod
    def target_profile(cls, value: str) -> str:
        if not PROFILE_RE.fullmatch(value):
            raise ValueError("invalid target profile")
        return value


class BuildRequest(BaseModel):
    request: str = Field(min_length=1, max_length=100_000)
    user_label: str | None = Field(default=None, max_length=200)


class RunRequest(BaseModel):
    app_id: str
    input: str = Field(min_length=1, max_length=100_000)
    scenario_id: str | None = Field(default=None, max_length=200)
    memory_scope: str | None = Field(default=None, max_length=256)
    user_label: str | None = Field(default=None, max_length=200)


class FeedbackRequest(BaseModel):
    outcome: Literal["success", "partial", "failure"]
    expected_result: str | None = Field(default=None, max_length=100_000)
    feedback: str | None = Field(default=None, max_length=100_000)


class ReviewRequest(BaseModel):
    app_id: str
    run_ids: list[str] = Field(min_length=1)
    feedback: str | None = Field(default=None, max_length=100_000)
