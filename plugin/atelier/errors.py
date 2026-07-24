from __future__ import annotations

from typing import Any

ERROR_TYPES = {
    "builder_failed",
    "profile_install_failed",
    "profile_unhealthy",
    "root_run_failed",
    "child_call_failed",
    "child_timeout",
    "child_cancelled",
    "trace_degraded",
    "review_failed",
    "proposal_invalid",
    "patch_apply_failed",
    "replay_failed",
    "incompatible_hermes",
    "call_not_allowed",
    "invalid_session",
    "endpoint_unavailable",
}


class AtelierError(Exception):
    def __init__(
        self,
        error_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if error_type not in ERROR_TYPES:
            raise ValueError(f"unknown Atelier error type: {error_type}")
        self.error_type = error_type
        self.message = message
        self.details = details
        super().__init__(self.message)

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "ok": False,
            "error_type": self.error_type,
            "message": self.message,
        }
        if self.details:
            value["details"] = self.details
        return value


def normalize_error(exc: Exception, fallback: str) -> dict[str, Any]:
    if isinstance(exc, AtelierError):
        return exc.as_dict()
    return AtelierError(fallback, str(exc) or type(exc).__name__).as_dict()
