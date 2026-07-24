from __future__ import annotations

import sqlite3


def claim_next(connection: sqlite3.Connection, worker_id: str) -> str | None:
    """Atomically claim one pending job; measured performance is intentionally absent."""
    row = connection.execute(
        "SELECT id FROM review_jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    changed = connection.execute(
        "UPDATE review_jobs SET status = 'running', worker_id = ? "
        "WHERE id = ? AND status = 'pending'",
        (worker_id, row[0]),
    ).rowcount
    return row[0] if changed == 1 else None
