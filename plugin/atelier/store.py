from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import database_path
from .redaction import redact


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS atelier_apps (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    entry_profile TEXT NOT NULL,
    source_path TEXT NOT NULL,
    definition_revision TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_endpoints (
    profile TEXT PRIMARY KEY,
    app_id TEXT,
    host TEXT NOT NULL CHECK (host = '127.0.0.1'),
    port INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL,
    pid INTEGER,
    last_error TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES atelier_apps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS atelier_runs (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    scenario_id TEXT,
    root_profile TEXT NOT NULL,
    root_session_id TEXT NOT NULL UNIQUE,
    root_hermes_run_id TEXT,
    definition_revision TEXT NOT NULL,
    status TEXT NOT NULL,
    user_label TEXT,
    input_text TEXT NOT NULL,
    memory_scope TEXT,
    output_text TEXT,
    error_type TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    FOREIGN KEY (app_id) REFERENCES atelier_apps(id)
);

CREATE TABLE IF NOT EXISTS atelier_spans (
    id TEXT PRIMARY KEY,
    atelier_run_id TEXT NOT NULL,
    parent_span_id TEXT,
    source_profile TEXT NOT NULL,
    target_profile TEXT NOT NULL,
    source_session_id TEXT NOT NULL,
    target_session_id TEXT NOT NULL UNIQUE,
    target_hermes_run_id TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    request_summary TEXT NOT NULL,
    response_summary TEXT,
    error_type TEXT,
    FOREIGN KEY (atelier_run_id) REFERENCES atelier_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_span_id) REFERENCES atelier_spans(id)
);

CREATE TABLE IF NOT EXISTS atelier_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atelier_run_id TEXT NOT NULL,
    span_id TEXT,
    profile TEXT NOT NULL,
    hermes_run_id TEXT,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (atelier_run_id) REFERENCES atelier_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (span_id) REFERENCES atelier_spans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS atelier_events_run_id_idx
    ON atelier_events(atelier_run_id, id);

CREATE TABLE IF NOT EXISTS atelier_reviews (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    run_ids TEXT NOT NULL,
    reviewer_session_id TEXT NOT NULL,
    reviewer_hermes_run_id TEXT,
    status TEXT NOT NULL,
    result_path TEXT,
    proposal_path TEXT,
    error_type TEXT,
    created_at TEXT NOT NULL,
    ended_at TEXT,
    FOREIGN KEY (app_id) REFERENCES atelier_apps(id)
);

CREATE TABLE IF NOT EXISTS builds (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    original_request TEXT NOT NULL,
    user_label TEXT,
    draft_path TEXT NOT NULL,
    builder_session_id TEXT NOT NULL,
    builder_hermes_run_id TEXT,
    builder_output TEXT,
    app_id TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_feedback (
    run_id TEXT PRIMARY KEY,
    outcome TEXT NOT NULL,
    expected_result TEXT,
    feedback TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES atelier_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    review_id TEXT,
    status TEXT NOT NULL,
    patch_path TEXT NOT NULL,
    approved_at TEXT,
    applied_at TEXT,
    apply_result TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES atelier_apps(id),
    FOREIGN KEY (review_id) REFERENCES atelier_reviews(id)
);
"""


class AtelierStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or database_path()).resolve()
        self._init_lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.executescript(SCHEMA)
                row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
                if row is None:
                    connection.execute("INSERT INTO schema_meta(version) VALUES (1)")
                elif row[0] != 1:
                    raise RuntimeError(f"unsupported Atelier schema version: {row[0]}")
            self._initialized = True

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def upsert_app(
        self,
        *,
        app_id: str,
        display_name: str,
        entry_profile: str,
        source_path: str,
        definition_revision: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO atelier_apps(
                    id, display_name, entry_profile, source_path, definition_revision,
                    definition_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name=excluded.display_name,
                    entry_profile=excluded.entry_profile,
                    source_path=excluded.source_path,
                    definition_revision=excluded.definition_revision,
                    definition_json=excluded.definition_json,
                    updated_at=excluded.updated_at
                """,
                (
                    app_id,
                    display_name,
                    entry_profile,
                    source_path,
                    definition_revision,
                    json.dumps(definition, ensure_ascii=False, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_app(app_id)  # type: ignore[return-value]

    def get_app(self, app_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM atelier_apps WHERE id = ?", (app_id,)
            ).fetchone()
        return self._row(row)

    def list_apps(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM atelier_apps ORDER BY id").fetchall()
        return [self._row(row) for row in rows]

    def delete_app(self, app_id: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM atelier_apps WHERE id = ?", (app_id,))

    def set_endpoint(
        self,
        *,
        profile: str,
        app_id: str | None,
        host: str,
        port: int,
        status: str = "stopped",
        pid: int | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO profile_endpoints(
                    profile, app_id, host, port, status, pid, last_error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile) DO UPDATE SET
                    app_id=excluded.app_id, host=excluded.host, port=excluded.port,
                    status=excluded.status, pid=excluded.pid, last_error=excluded.last_error,
                    updated_at=excluded.updated_at
                """,
                (profile, app_id, host, port, status, pid, last_error, now_iso()),
            )
        return self.get_endpoint(profile)  # type: ignore[return-value]

    def update_endpoint_status(
        self, profile: str, status: str, *, pid: int | None = None, last_error: str | None = None
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE profile_endpoints
                SET status=?, pid=?, last_error=?, updated_at=?
                WHERE profile=?
                """,
                (status, pid, last_error, now_iso(), profile),
            )

    def get_endpoint(self, profile: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profile_endpoints WHERE profile = ?", (profile,)
            ).fetchone()
        return self._row(row)

    def delete_endpoint(self, profile: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM profile_endpoints WHERE profile = ?", (profile,))

    def list_endpoints(self, app_id: str | None = None) -> list[dict[str, Any]]:
        self.initialize()
        sql = "SELECT * FROM profile_endpoints"
        params: tuple[Any, ...] = ()
        if app_id is not None:
            sql += " WHERE app_id = ?"
            params = (app_id,)
        sql += " ORDER BY profile"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def create_run(
        self,
        *,
        app_id: str,
        scenario_id: str | None,
        root_profile: str,
        definition_revision: str,
        input_text: str,
        memory_scope: str | None,
        user_label: str | None,
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex
        session_id = f"at_{run_id}_root"
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO atelier_runs(
                    id, app_id, scenario_id, root_profile, root_session_id,
                    definition_revision, status, user_label, input_text, memory_scope, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    app_id,
                    scenario_id,
                    root_profile,
                    session_id,
                    definition_revision,
                    user_label,
                    input_text,
                    memory_scope,
                    now_iso(),
                ),
            )
        return self.get_run(run_id)  # type: ignore[return-value]

    def update_run(self, run_id: str, **fields: Any) -> None:
        allowed = {
            "root_hermes_run_id",
            "status",
            "output_text",
            "error_type",
            "ended_at",
        }
        self._update("atelier_runs", "id", run_id, fields, allowed)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM atelier_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return self._row(row)

    def list_runs(self, app_id: str | None = None) -> list[dict[str, Any]]:
        self.initialize()
        sql = "SELECT * FROM atelier_runs"
        params: tuple[Any, ...] = ()
        if app_id:
            sql += " WHERE app_id = ?"
            params = (app_id,)
        sql += " ORDER BY started_at DESC"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def create_span(
        self,
        *,
        atelier_run_id: str,
        parent_span_id: str | None,
        source_profile: str,
        target_profile: str,
        source_session_id: str,
        request_summary: str,
    ) -> dict[str, Any]:
        span_id = uuid.uuid4().hex
        target_session_id = f"at_{atelier_run_id}_{span_id}"
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO atelier_spans(
                    id, atelier_run_id, parent_span_id, source_profile, target_profile,
                    source_session_id, target_session_id, status, started_at, request_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    span_id,
                    atelier_run_id,
                    parent_span_id,
                    source_profile,
                    target_profile,
                    source_session_id,
                    target_session_id,
                    now_iso(),
                    request_summary,
                ),
            )
        return self.get_span(span_id)  # type: ignore[return-value]

    def update_span(self, span_id: str, **fields: Any) -> None:
        allowed = {
            "target_hermes_run_id",
            "status",
            "ended_at",
            "response_summary",
            "error_type",
        }
        self._update("atelier_spans", "id", span_id, fields, allowed)

    def get_span(self, span_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM atelier_spans WHERE id = ?", (span_id,)
            ).fetchone()
        return self._row(row)

    def find_span_by_session(self, session_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM atelier_spans WHERE target_session_id = ?", (session_id,)
            ).fetchone()
        return self._row(row)

    def list_spans(self, run_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM atelier_spans WHERE atelier_run_id = ? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def add_event(
        self,
        *,
        atelier_run_id: str,
        span_id: str | None,
        profile: str,
        hermes_run_id: str | None,
        event_type: str,
        timestamp: str | float | None,
        payload: dict[str, Any],
    ) -> int:
        safe_payload = redact(payload)
        event_timestamp = str(timestamp) if timestamp is not None else now_iso()
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO atelier_events(
                    atelier_run_id, span_id, profile, hermes_run_id,
                    event_type, timestamp, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    atelier_run_id,
                    span_id,
                    profile,
                    hermes_run_id,
                    event_type,
                    event_timestamp,
                    json.dumps(safe_payload, ensure_ascii=False, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def list_events(self, run_id: str, *, after_id: int = 0) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM atelier_events
                WHERE atelier_run_id = ? AND id > ? ORDER BY id
                """,
                (run_id, after_id),
            ).fetchall()
        result = [self._row(row) for row in rows]
        for item in result:
            item["payload"] = json.loads(item.pop("payload_json"))
        return result

    def set_feedback(
        self,
        run_id: str,
        *,
        outcome: str,
        expected_result: str | None,
        feedback: str | None,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO run_feedback(run_id, outcome, expected_result, feedback, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    outcome=excluded.outcome,
                    expected_result=excluded.expected_result,
                    feedback=excluded.feedback,
                    updated_at=excluded.updated_at
                """,
                (run_id, outcome, expected_result, feedback, now_iso()),
            )

    def get_feedback(self, run_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM run_feedback WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row(row)

    def create_build(
        self,
        *,
        original_request: str,
        user_label: str | None,
        draft_path: str,
    ) -> dict[str, Any]:
        build_id = uuid.uuid4().hex
        session_id = f"atelier_build_{build_id}"
        timestamp = now_iso()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO builds(
                    id, status, original_request, user_label, draft_path,
                    builder_session_id, created_at, updated_at
                ) VALUES (?, 'draft', ?, ?, ?, ?, ?, ?)
                """,
                (
                    build_id,
                    original_request,
                    user_label,
                    draft_path,
                    session_id,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_build(build_id)  # type: ignore[return-value]

    def update_build(self, build_id: str, **fields: Any) -> None:
        fields["updated_at"] = now_iso()
        allowed = {
            "status",
            "builder_hermes_run_id",
            "builder_output",
            "app_id",
            "last_error",
            "updated_at",
        }
        self._update("builds", "id", build_id, fields, allowed)

    def get_build(self, build_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
        return self._row(row)

    def list_builds(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM builds ORDER BY created_at DESC").fetchall()
        return [self._row(row) for row in rows]

    def create_review(self, *, app_id: str, run_ids: list[str]) -> dict[str, Any]:
        review_id = uuid.uuid4().hex
        session_id = f"atelier_review_{review_id}"
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO atelier_reviews(
                    id, app_id, run_ids, reviewer_session_id, status, created_at
                ) VALUES (?, ?, ?, ?, 'queued', ?)
                """,
                (review_id, app_id, json.dumps(run_ids), session_id, now_iso()),
            )
        return self.get_review(review_id)  # type: ignore[return-value]

    def update_review(self, review_id: str, **fields: Any) -> None:
        allowed = {
            "reviewer_hermes_run_id",
            "status",
            "result_path",
            "proposal_path",
            "error_type",
            "ended_at",
        }
        self._update("atelier_reviews", "id", review_id, fields, allowed)

    def get_review(self, review_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM atelier_reviews WHERE id = ?", (review_id,)
            ).fetchone()
        value = self._row(row)
        if value:
            value["run_ids"] = json.loads(value["run_ids"])
        return value

    def create_proposal(
        self,
        *,
        app_id: str,
        review_id: str | None,
        patch_path: str,
        proposal_id: str | None = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        proposal_id = proposal_id or uuid.uuid4().hex
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO proposals(id, app_id, review_id, status, patch_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (proposal_id, app_id, review_id, status, patch_path, now_iso()),
            )
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    def update_proposal(self, proposal_id: str, **fields: Any) -> None:
        allowed = {"status", "approved_at", "applied_at", "apply_result"}
        self._update("proposals", "id", proposal_id, fields, allowed)

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return self._row(row)

    def list_proposals(self, app_id: str | None = None) -> list[dict[str, Any]]:
        self.initialize()
        sql = "SELECT * FROM proposals"
        params: tuple[Any, ...] = ()
        if app_id:
            sql += " WHERE app_id = ?"
            params = (app_id,)
        sql += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def _update(
        self,
        table: str,
        key_name: str,
        key_value: str,
        fields: dict[str, Any],
        allowed: Iterable[str],
    ) -> None:
        allowed_set = set(allowed)
        unknown = set(fields) - allowed_set
        if unknown:
            raise ValueError(f"unsupported {table} fields: {sorted(unknown)}")
        if not fields:
            return
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = [fields[key] for key in fields]
        with self.transaction() as connection:
            cursor = connection.execute(
                f"UPDATE {table} SET {columns} WHERE {key_name} = ?",  # noqa: S608
                (*values, key_value),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"{table} row not found: {key_value}")

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None
