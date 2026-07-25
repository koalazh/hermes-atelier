from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .redaction import redact


def _now() -> str:
    return datetime.now(UTC).isoformat()


class StudioStore:
    """Project-local V2 design and evaluation evidence, never application runtime state."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._lock = threading.Lock()

    def _directory(self, kind: str) -> Path:
        directory = self.root / kind
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(redact(value), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError(f"expected JSON object: {path}")
        return value

    def create_design(self, *, requirement: str) -> dict[str, Any]:
        design_id = uuid.uuid4().hex
        timestamp = _now()
        design = {
            "id": design_id,
            "status": "conversation",
            "requirement": requirement,
            "builder_session_id": f"atelier_design_{design_id}",
            "builder_turns": [],
            "drafter_run_ids": [],
            "messages": [],
            "plan_path": str(self._directory("designs") / design_id / "PLAN.md"),
            "draft_path": str(self._directory("designs") / design_id / "draft"),
            "candidate": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        self.save_design(design)
        return design

    def save_design(self, design: dict[str, Any]) -> None:
        design = {**design, "updated_at": _now()}
        with self._lock:
            self._write_json(self._directory("designs") / str(design["id"]) / "design.json", design)

    def get_design(self, design_id: str) -> dict[str, Any]:
        path = self._directory("designs") / design_id / "design.json"
        if not path.is_file():
            raise KeyError(f"unknown Design: {design_id}")
        return self._read_json(path)

    def list_designs(self) -> list[dict[str, Any]]:
        designs = []
        for path in self._directory("designs").glob("*/design.json"):
            designs.append(self._read_json(path))
        return sorted(designs, key=lambda item: item["updated_at"], reverse=True)

    def append_trace(self, event: dict[str, Any]) -> dict[str, Any]:
        source_session_id = str(event.get("source_session_id") or "").strip()
        call_id = str(event.get("call_id") or "").strip()
        event_type = str(event.get("event") or "").strip()
        if (
            not source_session_id
            or not call_id
            or event_type
            not in {
                "profile_call.started",
                "profile_call.completed",
                "profile_call.failed",
            }
        ):
            raise ValueError("invalid profile_call trace event")
        stored = {**event, "observed_at": _now()}
        path = self._directory("traces") / f"{source_session_id}.jsonl"
        with self._lock, path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(redact(stored), ensure_ascii=False) + "\n")
        return stored

    def traces(self, source_session_id: str) -> list[dict[str, Any]]:
        path = self._directory("traces") / f"{source_session_id}.jsonl"
        if not path.is_file():
            return []
        result = []
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
        return result

    def save_experiment(self, experiment: dict[str, Any]) -> None:
        with self._lock:
            self._write_json(
                self._directory("experiments") / f"{experiment['id']}.json",
                experiment,
            )

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        path = self._directory("experiments") / f"{experiment_id}.json"
        if not path.is_file():
            raise KeyError(f"unknown Experiment: {experiment_id}")
        return self._read_json(path)

    def list_experiments(self) -> list[dict[str, Any]]:
        values = [self._read_json(path) for path in self._directory("experiments").glob("*.json")]
        return sorted(values, key=lambda item: item["created_at"], reverse=True)
