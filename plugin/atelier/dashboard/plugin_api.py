from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.errors import AtelierError  # noqa: E402
from plugin.atelier.schemas import (  # noqa: E402
    BuildRequest,
    FeedbackRequest,
    ReviewRequest,
    RunRequest,
)
from plugin.atelier.services.apps import AppService  # noqa: E402
from plugin.atelier.services.builds import BuildService  # noqa: E402
from plugin.atelier.services.profiles import LOOPBACK, ProfileService  # noqa: E402
from plugin.atelier.services.proposals import ProposalService  # noqa: E402
from plugin.atelier.services.reviews import ReviewService  # noqa: E402
from plugin.atelier.services.runs import RunService  # noqa: E402
from plugin.atelier.store import AtelierStore  # noqa: E402

router = APIRouter()
store = AtelierStore()
apps = AppService(store)
profiles = ProfileService(store)
runs = RunService(store, profile_service=profiles, app_service=apps)
builds = BuildService(store, profiles=profiles, apps=apps)
reviews = ReviewService(store, profiles=profiles)
proposals = ProposalService(store, profiles=profiles, apps=apps, reviews=reviews)


def _assert_loopback() -> None:
    configured = (
        os.environ.get("HERMES_DASHBOARD_HOST") or os.environ.get("DASHBOARD_HOST") or LOOPBACK
    )
    if configured not in {LOOPBACK, "localhost", "::1"}:
        raise HTTPException(status_code=403, detail="Atelier V1 requires a loopback Dashboard")


def _api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ValueError, AtelierError)):
        detail = exc.as_dict() if isinstance(exc, AtelierError) else str(exc)
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=500, detail="Atelier operation failed")


@router.get("/apps")
async def list_apps():
    _assert_loopback()
    return {"items": apps.list()}


@router.get("/apps/{app_id}")
async def get_app(app_id: str):
    _assert_loopback()
    try:
        return apps.get(app_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/builds", status_code=202)
async def create_build(request: BuildRequest):
    _assert_loopback()
    try:
        return builds.create(request)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.get("/builds/{build_id}")
async def get_build(build_id: str):
    _assert_loopback()
    try:
        return builds.detail(build_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/builds/{build_id}/approve")
async def approve_build(build_id: str):
    _assert_loopback()
    try:
        return builds.approve(build_id)
    except Exception as exc:
        raise _api_error(exc) from exc


def _app_profiles(app_id: str):
    definition = apps.get_definition(app_id)
    return [profile.name for profile in definition.profiles]


@router.post("/apps/{app_id}/start")
async def start_app(app_id: str):
    _assert_loopback()
    try:
        return {"items": [profiles.start(profile) for profile in _app_profiles(app_id)]}
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/apps/{app_id}/stop")
async def stop_app(app_id: str):
    _assert_loopback()
    try:
        return {"items": [profiles.stop(profile) for profile in _app_profiles(app_id)]}
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/apps/{app_id}/restart")
async def restart_app(app_id: str):
    _assert_loopback()
    try:
        return {"items": [profiles.restart(profile) for profile in _app_profiles(app_id)]}
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/profiles/{profile}/start")
async def start_profile(profile: str):
    _assert_loopback()
    try:
        return profiles.start(profile)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/profiles/{profile}/stop")
async def stop_profile(profile: str):
    _assert_loopback()
    try:
        return profiles.stop(profile)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/profiles/{profile}/restart")
async def restart_profile(profile: str):
    _assert_loopback()
    try:
        return profiles.restart(profile)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/runs", status_code=202)
async def create_run(request: RunRequest):
    _assert_loopback()
    try:
        return runs.start_root(request)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.get("/runs")
async def list_runs(app_id: str | None = Query(default=None)):
    _assert_loopback()
    return {"items": store.list_runs(app_id)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    _assert_loopback()
    try:
        return runs.detail(run_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str):
    _assert_loopback()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def stream():
        cursor = 0
        idle_after_terminal = 0
        while True:
            events = store.list_events(run_id, after_id=cursor)
            for event in events:
                cursor = event["id"]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            run = store.get_run(run_id)
            terminal = run and run["status"] in {
                "completed",
                "failed",
                "cancelled",
                "trace_degraded",
            }
            if terminal and not events:
                idle_after_terminal += 1
                if idle_after_terminal >= 2:
                    yield f"event: terminal\ndata: {json.dumps({'status': run['status']})}\n\n"
                    break
            else:
                idle_after_terminal = 0
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/stop", status_code=202)
async def stop_run(run_id: str):
    _assert_loopback()
    try:
        return await runs.stop(run_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/runs/{run_id}/feedback")
async def add_feedback(run_id: str, request: FeedbackRequest):
    _assert_loopback()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    store.set_feedback(run_id, **request.model_dump())
    return store.get_feedback(run_id)


@router.post("/runs/{run_id}/replay", status_code=202)
async def replay_run(run_id: str):
    _assert_loopback()
    source = store.get_run(run_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        replay = runs.start_root(
            RunRequest(
                app_id=source["app_id"],
                input=source["input_text"],
                scenario_id=source["scenario_id"],
                memory_scope=source["memory_scope"],
                user_label=f"Replay of {run_id[:8]}",
            )
        )
        return {"source_run_id": run_id, "replay": replay}
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/reviews", status_code=202)
async def create_review(request: ReviewRequest):
    _assert_loopback()
    try:
        return reviews.create(request)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.get("/reviews/{review_id}")
async def get_review(review_id: str):
    _assert_loopback()
    try:
        return reviews.detail(review_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/reviews/{review_id}/proposals", status_code=202)
async def request_proposal(review_id: str):
    _assert_loopback()
    try:
        return proposals.request(review_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str):
    _assert_loopback()
    try:
        return proposals.detail(proposal_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/proposals/{proposal_id}/apply")
async def apply_proposal(proposal_id: str):
    _assert_loopback()
    try:
        return proposals.apply(proposal_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str):
    _assert_loopback()
    try:
        return proposals.reject(proposal_id)
    except Exception as exc:
        raise _api_error(exc) from exc


@router.post("/proposals/{proposal_id}/revert")
async def revert_proposal(proposal_id: str):
    _assert_loopback()
    try:
        return proposals.revert(proposal_id)
    except Exception as exc:
        raise _api_error(exc) from exc
