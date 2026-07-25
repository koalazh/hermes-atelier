"""Small SQLite-backed review queue; measured performance is intentionally absent."""


def claim_sql() -> str:
    return "UPDATE review_jobs SET status='running' WHERE id=? AND status='pending'"
