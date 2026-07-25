from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.app_pack import AppPack, build_definition_snapshot, release_pack  # noqa: E402
from plugin.atelier.designs import DesignService  # noqa: E402
from plugin.atelier.evaluation import ExperimentService, load_case  # noqa: E402
from plugin.atelier.paths import apps_root, atelier_root, ensure_within  # noqa: E402
from plugin.atelier.studio_store import StudioStore  # noqa: E402

router = APIRouter()
store = StudioStore(atelier_root() / "v2")


class DesignCreate(BaseModel):
    requirement: str = Field(min_length=1, max_length=100_000)


class DesignMessage(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class CandidateRecord(BaseModel):
    branch: str = Field(min_length=1, max_length=500)
    worktree: str = Field(min_length=1, max_length=2000)
    diff_summary: str = Field(max_length=100_000)


class ExperimentCreate(BaseModel):
    pack_id: str
    case_id: str
    entry_base_url: str
    api_key_env: str
    model_fingerprint: dict[str, Any]
    trial_count: int = Field(default=1, ge=1, le=20)
    candidate: dict[str, str] | None = None


class Feedback(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class ReleaseRequest(BaseModel):
    git_revision: str | None = Field(default=None, max_length=200)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ValueError, RuntimeError)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Atelier V2 operation failed")


def _designs() -> DesignService:
    base_url = os.environ.get("ATELIER_BUILDER_URL", "").strip()
    key_env = os.environ.get("ATELIER_BUILDER_KEY_ENV", "ATELIER_BUILDER_API_KEY")
    api_key = os.environ.get(key_env, "")
    if not base_url or not api_key:
        raise ValueError("configure ATELIER_BUILDER_URL and the ATELIER_BUILDER_KEY_ENV secret")
    drafter_url = os.environ.get("ATELIER_DRAFTER_URL", "").strip()
    drafter_key_env = os.environ.get("ATELIER_DRAFTER_KEY_ENV", "ATELIER_DRAFTER_API_KEY")
    drafter_key = os.environ.get(drafter_key_env, "")
    return DesignService(
        store,
        builder_base_url=base_url,
        builder_api_key=api_key,
        drafter_base_url=drafter_url or None,
        drafter_api_key=drafter_key or None,
    )


def _pack(pack_id: str) -> AppPack:
    root = ensure_within(apps_root() / pack_id, apps_root())
    return AppPack.load(root)


def _pack_summary(pack: AppPack) -> dict[str, Any]:
    return {
        "id": pack.manifest.id,
        "version": pack.manifest.version,
        "entry": pack.manifest.entry,
        "agents": pack.manifest.model_dump(mode="json")["agents"],
        "public_api": pack.manifest.public_api.model_dump(mode="json"),
        "state_policy": pack.manifest.state_policy,
        "cases": pack.manifest.cases,
        "revision": build_definition_snapshot(pack)["revision"],
    }


@router.get("/overview")
async def overview():
    packs = []
    if apps_root().is_dir():
        for child in sorted(apps_root().iterdir()):
            if child.is_dir() and (child / "app.yaml").is_file():
                try:
                    packs.append(_pack_summary(AppPack.load(child)))
                except (ValueError, OSError):
                    continue
    return {
        "packs": packs,
        "designs": store.list_designs(),
        "experiments": store.list_experiments(),
    }


@router.post("/designs", status_code=201)
async def create_design(request: DesignCreate):
    try:
        return _designs().create(request.requirement)
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/designs/{design_id}")
async def get_design(design_id: str):
    try:
        return _designs().detail(design_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/designs/{design_id}/messages")
async def design_message(design_id: str, request: DesignMessage):
    try:
        return await _designs().message(design_id, request.content)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/designs/{design_id}/generate-draft")
async def generate_draft(design_id: str):
    try:
        return await _designs().generate_draft(design_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/designs/{design_id}/candidate")
async def record_candidate(design_id: str, request: CandidateRecord):
    try:
        return _designs().record_candidate(design_id, **request.model_dump())
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/traces", status_code=202)
async def ingest_trace(event: dict[str, Any]):
    try:
        return store.append_trace(event)
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/sessions/{session_id}/traces")
async def session_traces(session_id: str):
    return {"items": store.traces(session_id)}


@router.post("/experiments", status_code=201)
async def run_experiment(request: ExperimentCreate):
    try:
        pack = _pack(request.pack_id)
        matching = [
            relative for relative in pack.manifest.cases if Path(relative).stem == request.case_id
        ]
        if len(matching) != 1:
            raise ValueError(f"unknown Case: {request.case_id}")
        api_key = os.environ.get(request.api_key_env, "")
        if not api_key:
            raise ValueError(f"missing API key environment: {request.api_key_env}")
        return await ExperimentService(store).run(
            pack_root=pack.root,
            case_path=pack.root / matching[0],
            entry_base_url=request.entry_base_url,
            api_key=api_key,
            model_fingerprint=request.model_fingerprint,
            trial_count=request.trial_count,
            candidate=request.candidate,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    try:
        return store.get_experiment(experiment_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/experiments/{experiment_id}/feedback")
async def experiment_feedback(experiment_id: str, request: Feedback):
    try:
        return ExperimentService(store).feedback(experiment_id, request.content)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/experiments/{experiment_id}/review")
async def review_experiment(experiment_id: str):
    try:
        base_url = os.environ.get("ATELIER_REVIEWER_URL", "").strip()
        key_env = os.environ.get("ATELIER_REVIEWER_KEY_ENV", "ATELIER_REVIEWER_API_KEY")
        api_key = os.environ.get(key_env, "")
        if not base_url or not api_key:
            raise ValueError(
                "configure ATELIER_REVIEWER_URL and the ATELIER_REVIEWER_KEY_ENV secret"
            )
        return await ExperimentService(store).review(
            experiment_id,
            reviewer_base_url=base_url,
            reviewer_api_key=api_key,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/packs/{pack_id}/release", status_code=201)
async def release(pack_id: str, request: ReleaseRequest):
    try:
        pack = _pack(pack_id)
        destination = atelier_root() / "releases" / f"{pack_id}-{pack.manifest.version}"
        return release_pack(pack, destination, git_revision=request.git_revision)
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/packs/{pack_id}/cases")
async def pack_cases(pack_id: str):
    try:
        pack = _pack(pack_id)
        items = []
        for relative in pack.manifest.cases:
            case, digest = load_case(pack.root / relative)
            items.append({**case.model_dump(mode="json"), "hash": digest})
        return {"items": items}
    except Exception as exc:
        raise _error(exc) from exc
