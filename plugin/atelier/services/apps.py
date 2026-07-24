from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..paths import apps_root, ensure_within
from ..schemas import AppDefinition, load_app_definition
from ..store import AtelierStore


def definition_revision(definition: AppDefinition) -> str:
    body = json.dumps(definition.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:16]


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
            definition_revision=definition_revision(definition),
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
        return value

    def list(self) -> list[dict[str, Any]]:
        result = []
        for app in self.store.list_apps():
            value = dict(app)
            value.pop("definition_json", None)
            value["endpoints"] = self.store.list_endpoints(app["id"])
            result.append(value)
        return result
