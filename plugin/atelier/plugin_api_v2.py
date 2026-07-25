from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .app_pack import AppPack, build_definition_snapshot, release_pack
from .designs import DesignService
from .evaluation import ExperimentService, load_case
from .hermes_http import HermesHTTPClient
from .pack_app import PackRuntime
from .paths import apps_root, atelier_root, ensure_within
from .studio_store import StudioStore

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


class ExperimentCandidate(BaseModel):
    branch: str = Field(min_length=1, max_length=500)
    worktree: str = Field(min_length=1, max_length=2000)
    commit: str = Field(min_length=40, max_length=64, pattern=r"^[0-9a-f]+$")
    baseline_commit: str = Field(min_length=40, max_length=64, pattern=r"^[0-9a-f]+$")
    baseline_source_revision: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]+$")
    baseline_case_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]+$")


class ExperimentCreate(BaseModel):
    pack_id: str
    case_id: str
    runtime_instance: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    trial_count: int = Field(default=1, ge=1, le=20)
    candidate: ExperimentCandidate | None = None


class Feedback(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class ReleaseRequest(BaseModel):
    git_revision: str | None = Field(default=None, max_length=200)


class CaseRunRequest(BaseModel):
    case_id: str | None = None


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


def _runtime(instance: str) -> PackRuntime:
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser().resolve()
    state = ensure_within(home / "app-packs" / instance, home / "app-packs")
    install_path = state / "install.json"
    if not install_path.is_file():
        raise ValueError(f"App Pack runtime instance is not installed: {instance}")
    install = json.loads(install_path.read_text(encoding="utf-8"))
    if not isinstance(install, dict) or not install.get("pack_path"):
        raise ValueError(f"invalid App Pack install state: {instance}")
    return PackRuntime(Path(str(install["pack_path"])), hermes_home=home)


def _installed_instances(pack_id: str | None = None) -> list[dict[str, Any]]:
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser().resolve()
    root = home / "app-packs"
    if not root.is_dir():
        return []
    values = []
    for state in sorted(root.iterdir()):
        install_path = state / "install.json"
        lock_path = state / "app.lock"
        if not install_path.is_file() or not lock_path.is_file():
            continue
        try:
            install = json.loads(install_path.read_text(encoding="utf-8"))
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if not isinstance(install, dict) or not isinstance(lock, dict):
                continue
            if pack_id and lock.get("pack_id") != pack_id:
                continue
            runtime_path = state / "runtime.json"
            runtime = (
                json.loads(runtime_path.read_text(encoding="utf-8"))
                if runtime_path.is_file()
                else None
            )
            pack_path = Path(str(install.get("pack_path") or "")).resolve()
            levels = ["packed", "installed"]
            if pack_path.is_dir() and (pack_path / "app.lock").is_file():
                levels = PackRuntime(pack_path, hermes_home=home).evidence_levels(state.name)
            values.append(
                {
                    "instance": state.name,
                    "pack_id": lock.get("pack_id"),
                    "pack_version": lock.get("pack_version"),
                    "entry": lock.get("manifest", {}).get("entry"),
                    "entry_profile": (
                        f"{state.name}--{lock.get('manifest', {}).get('entry')}"
                    ),
                    "entry_base_url": (
                        runtime.get("entry_base_url")
                        if isinstance(runtime, dict)
                        else None
                    ),
                    "evidence_levels": levels,
                    "fresh_instance": install.get("fresh_instance") is True,
                    "configured": isinstance(runtime, dict),
                }
            )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return values


def _runtime_api_key(instance: str) -> tuple[str, str]:
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser().resolve()
    state = ensure_within(home / "app-packs" / instance, home / "app-packs")
    lock = json.loads((state / "app.lock").read_text(encoding="utf-8"))
    runtime = json.loads((state / "runtime.json").read_text(encoding="utf-8"))
    entry = str(lock["manifest"]["entry"])
    profile = home / "profiles" / f"{instance}--{entry}"
    key_env = str(runtime.get("entry_gateway_key_env") or runtime["gateway_key_env"])
    values = {}
    for line in (profile / ".env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    key = values.get(key_env, "")
    if not key:
        raise ValueError(f"entry Gateway credential is unavailable for instance: {instance}")
    return str(runtime["entry_base_url"]), key


def _trace_visibility(events: list[dict[str, Any]]) -> str:
    if not events:
        return "unobserved_collaboration_possible"
    started = {
        str(event.get("call_id"))
        for event in events
        if event.get("event") == "profile_call.started"
    }
    finished = {
        str(event.get("call_id"))
        for event in events
        if event.get("event") in {"profile_call.completed", "profile_call.failed"}
    }
    return "complete_trace" if started and started <= finished else "partial_trace"


def _pack_summary(pack: AppPack) -> dict[str, Any]:
    return {
        "id": pack.manifest.id,
        "version": pack.manifest.version,
        "entry": pack.manifest.entry,
        "agents": pack.manifest.model_dump(mode="json")["agents"],
        "public_api": pack.manifest.public_api.model_dump(mode="json"),
        "state_policy": pack.manifest.state_policy,
        "state_compatibility": pack.manifest.state_compatibility,
        "allowed_calls": pack.manifest.allowed_calls,
        "collaboration": pack.manifest.collaboration,
        "cases": pack.manifest.cases,
        "revision": build_definition_snapshot(pack)["revision"],
        "evidence_levels": ["packed"],
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
        "instances": _installed_instances(),
        "designs": store.list_designs(),
        "experiments": store.list_experiments(),
    }


@router.get("/packs/{pack_id}/workspace")
async def pack_workspace(pack_id: str):
    try:
        pack = _pack(pack_id)
        instances = _installed_instances(pack_id)
        sessions: list[dict[str, Any]] = []
        session_discovery = {
            "status": "unavailable",
            "reason": "No configured runtime instance was discovered.",
        }
        selected = next(
            (item for item in instances if item.get("configured")),
            None,
        )
        if selected:
            try:
                base_url, api_key = _runtime_api_key(str(selected["instance"]))
                sessions = await HermesHTTPClient(base_url, api_key).sessions(limit=20)
                session_discovery = {
                    "status": "available",
                    "instance": selected["instance"],
                }
            except Exception as exc:
                session_discovery = {
                    "status": "unavailable",
                    "reason": str(exc),
                    "instance": selected["instance"],
                }
        cases = []
        for relative in pack.manifest.cases:
            case, digest = load_case(pack.root / relative)
            cases.append({**case.model_dump(mode="json"), "hash": digest})
        releases_root = atelier_root() / "releases"
        releases = (
            [
                {"path": str(path), "name": path.name}
                for path in sorted(releases_root.glob(f"{pack_id}-*"))
                if (path / "app.lock").is_file()
            ]
            if releases_root.is_dir()
            else []
        )
        return {
            "pack": _pack_summary(pack),
            "instances": instances,
            "sessions": sessions,
            "session_discovery": session_discovery,
            "designs": store.list_designs(),
            "cases": cases,
            "releases": releases,
        }
    except Exception as exc:
        raise _error(exc) from exc


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
    items = store.traces(session_id)
    return {
        "items": items,
        "visibility": _trace_visibility(items),
        "notice": (
            "Only visible profile_call events are shown. Native delegation, Kanban, MCP, "
            "or other collaboration may be unobserved."
        ),
    }


@router.post("/instances/{instance}/attest")
async def attest_instance(instance: str):
    try:
        return _runtime(instance).attest(instance=instance)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/instances/{instance}/live-probe")
async def live_probe_instance(instance: str):
    try:
        return _runtime(instance).live_probe(instance=instance)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/instances/{instance}/cases")
async def run_instance_cases(instance: str, request: CaseRunRequest):
    try:
        return _runtime(instance).run_cases(
            instance=instance,
            case_id=request.case_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/experiments", status_code=201)
async def run_experiment(request: ExperimentCreate):
    try:
        pack = _pack(request.pack_id)
        candidate = request.candidate.model_dump() if request.candidate else None
        if candidate:
            repository = subprocess.run(
                ["git", "-C", str(pack.root), "rev-parse", "--show-toplevel"],
                check=False,
                capture_output=True,
                text=True,
            )
            if repository.returncode != 0:
                raise ValueError("baseline App Pack must belong to Git")
            relative = pack.root.relative_to(Path(repository.stdout.strip()).resolve())
            worktree = Path(candidate["worktree"]).expanduser().resolve()
            pack = AppPack.load(ensure_within(worktree / relative, worktree))
        matching = [
            relative for relative in pack.manifest.cases if Path(relative).stem == request.case_id
        ]
        if len(matching) != 1:
            raise ValueError(f"unknown Case: {request.case_id}")
        runtime = _runtime(request.runtime_instance)
        attestation = runtime.attest(instance=request.runtime_instance)
        key_env = str(attestation["gateway_key_env"])
        api_key = os.environ.get(key_env, "")
        if not api_key:
            raise ValueError(f"missing API key environment: {key_env}")
        return await ExperimentService(store).run(
            pack_root=pack.root,
            case_path=pack.root / matching[0],
            api_key=api_key,
            runtime_attestation=attestation,
            trial_count=request.trial_count,
            candidate=candidate,
            attestation_refresh=lambda: runtime.attest(instance=request.runtime_instance),
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
        result = release_pack(pack, destination, git_revision=request.git_revision)
        return {**result, "evidence_levels": ["packed"]}
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
