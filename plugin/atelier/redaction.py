from __future__ import annotations

import re
from typing import Any

_SECRET_KEY = re.compile(
    r"(?:authorization|api[-_]?key|access[-_]?token|refresh[-_]?token|password|secret)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_KNOWN_TOKEN = re.compile(r"\b(?:sk|key|token)-[A-Za-z0-9_-]{12,}\b", re.IGNORECASE)
_ASSIGNMENT = re.compile(
    r"(?i)\b(API[_-]?KEY|AUTHORIZATION|PASSWORD|SECRET|TOKEN)\s*[:=]\s*([^\s,;]+)"
)


def redact_text(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _KNOWN_TOKEN.sub("[REDACTED]", value)
    return _ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SECRET_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    return value
