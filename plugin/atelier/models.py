from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AtelierApp:
    id: str
    display_name: str
    entry_profile: str
    source_path: str
    definition_revision: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AtelierRun:
    id: str
    app_id: str
    scenario_id: str | None
    root_profile: str
    root_session_id: str
    root_hermes_run_id: str | None
    definition_revision: str
    status: str
    user_label: str | None
    started_at: str
    ended_at: str | None


@dataclass(frozen=True, slots=True)
class AtelierSpan:
    id: str
    atelier_run_id: str
    parent_span_id: str | None
    source_profile: str
    target_profile: str
    source_session_id: str
    target_session_id: str
    target_hermes_run_id: str | None
    status: str
    started_at: str
    ended_at: str | None
    request_summary: str
    response_summary: str | None
    error_type: str | None


@dataclass(frozen=True, slots=True)
class AtelierEvent:
    id: int
    atelier_run_id: str
    span_id: str | None
    profile: str
    hermes_run_id: str | None
    event_type: str
    timestamp: str
    payload_json: str


@dataclass(frozen=True, slots=True)
class AtelierReview:
    id: str
    app_id: str
    run_ids: str
    reviewer_session_id: str
    status: str
    result_path: str | None
    proposal_path: str | None
    created_at: str
