from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from ..paths import apps_root, ensure_within
from ..schemas import AppDefinition, load_app_definition
from ..store import AtelierStore


def definition_revision(definition: AppDefinition, app_dir: Path) -> str:
    digest = hashlib.sha256(
        json.dumps(
            definition.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    )
    for path in sorted(item for item in app_dir.rglob("*") if item.is_file()):
        if path.name in {".env", "auth.json"} or path.is_symlink():
            continue
        digest.update(path.relative_to(app_dir).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


class AppService:
    def __init__(self, store: AtelierStore) -> None:
        self.store = store

    def register(self, app_dir: Path) -> dict[str, Any]:
        app_dir = ensure_within(app_dir, apps_root())
        definition_path = app_dir / "app.yaml"
        definition = load_app_definition(definition_path)
        if app_dir.name != definition.id:
            raise ValueError("application directory name must equal app id")
        return self.store.upsert_app(
            app_id=definition.id,
            display_name=definition.display_name,
            entry_profile=definition.entry_profile,
            source_path=str(app_dir),
            definition_revision=definition_revision(definition, app_dir),
            definition=definition.model_dump(mode="json"),
        )

    def register_all(self) -> list[dict[str, Any]]:
        root = apps_root()
        if not root.exists():
            return []
        registered = []
        for path in sorted(root.iterdir()):
            if path.is_dir() and not path.name.startswith(".") and (path / "app.yaml").is_file():
                registered.append(self.register(path))
        return registered

    def get_definition(self, app_id: str) -> AppDefinition:
        app = self.store.get_app(app_id)
        if app is None:
            raise KeyError(f"unknown application: {app_id}")
        return AppDefinition.model_validate(json.loads(app["definition_json"]))

    def get(self, app_id: str) -> dict[str, Any]:
        app = self.store.get_app(app_id)
        if app is None:
            raise KeyError(f"unknown application: {app_id}")
        value = dict(app)
        value["definition"] = json.loads(value.pop("definition_json"))
        value["endpoints"] = self.store.list_endpoints(app_id)
        value["scenarios"] = self.scenarios(app_id)
        return value

    def scenarios(self, app_id: str) -> list[dict[str, Any]]:
        app = self.store.get_app(app_id)
        if app is None:
            raise KeyError(f"unknown application: {app_id}")
        definition = self.get_definition(app_id)
        directory = ensure_within(
            Path(app["source_path"]) / definition.scenarios_dir,
            Path(app["source_path"]),
        )
        result = []
        for path in sorted(directory.glob("*.yaml")):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict) or not isinstance(loaded.get("input"), str):
                continue
            result.append(
                {
                    "id": path.stem,
                    "name": str(loaded.get("name") or path.stem),
                    "input": loaded["input"],
                    "expected": str(loaded.get("expected") or ""),
                    "memory_scope": loaded.get("memory_scope"),
                }
            )
        return result

    def list(self) -> list[dict[str, Any]]:
        result = []
        for app in self.store.list_apps():
            value = dict(app)
            value.pop("definition_json", None)
            value["endpoints"] = self.store.list_endpoints(app["id"])
            result.append(value)
        return result
