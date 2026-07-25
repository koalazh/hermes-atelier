from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from plugin.atelier.app_pack import AppPack, build_definition_snapshot
from plugin.atelier.designs import DesignService
from plugin.atelier.evaluation import ExperimentService, load_case
from plugin.atelier.studio_store import StudioStore
from tests.test_app_pack_v2 import create_pack


def runtime_attestation(pack_root: Path, case_path: Path) -> dict[str, Any]:
    snapshot = build_definition_snapshot(AppPack.load(pack_root))
    case, case_hash = load_case(case_path)
    return {
        "verified": True,
        "pack_id": "support",
        "pack_version": "2.0.0",
        "pack_revision": snapshot["revision"],
        "source_revision": snapshot["revision"],
        "source_provenance": {
            "kind": "content_sha256",
            "revision": snapshot["revision"],
        },
        "definition_snapshot": snapshot,
        "cases": [{"id": case.id, "hash": case_hash}],
        "model_fingerprint": {"provider": "custom", "model": "test-model"},
        "entry_base_url": "http://entry",
    }


def test_dashboard_api_loads_from_a_standalone_user_plugin(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "plugin" / "atelier"
    plugin = tmp_path / "plugins" / "atelier"
    shutil.copytree(source, plugin, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(tmp_path / 'plugins')!r}); "
                "from atelier.dashboard.plugin_api_v2 import router; "
                "assert router"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


class FakeBuilderClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.outputs = [
            "DESIGN_STATUS: NEEDS_INPUT\n\nWho will use the application?",
            (
                "Alignment complete.\nDESIGN_STATUS: PLAN_READY\n# Design Plan\n\n"
                "Users: support operators\n\nRisk: real API is missing."
            ),
            "Draft generated for inspection.",
        ]

    async def start_run(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if "explicitly selected Generate Draft" in kwargs["task"]:
            match = re.search(r"write only beneath (.+?)\. Generate", kwargs["task"])
            assert match
            create_pack(Path(match.group(1)) / "generated")
        return f"run_{len(self.calls)}"

    async def ensure_session(self, session_id: str, **_: Any) -> dict[str, Any]:
        return {"session": {"id": session_id}}

    async def chat_session(self, session_id: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"session_id": session_id, **kwargs})
        output = self.outputs[len(self.calls) - 1]
        return {"session_id": session_id, "message": {"content": output}}

    async def events(self, run_id: str):
        output = self.outputs[int(run_id.removeprefix("run_")) - 1]
        yield {"event": "message.delta", "delta": output}
        yield {"event": "run.completed", "status": "completed", "output": output}

    async def status(self, run_id: str) -> dict[str, Any]:
        return {"event": "run.completed", "status": "completed"}


@pytest.mark.asyncio
async def test_design_is_multiturn_and_generate_draft_is_explicit(tmp_path: Path) -> None:
    store = StudioStore(tmp_path / ".atelier" / "v2")
    client = FakeBuilderClient()
    service = DesignService(
        store,
        builder_base_url="http://builder",
        builder_api_key="runtime-secret",
        drafter_base_url="http://drafter",
        drafter_api_key="runtime-secret",
        client_factory=lambda *_: client,
    )

    design = service.create("Build a support application")
    assert design["status"] == "conversation"
    assert not Path(design["draft_path"]).exists()

    first = await service.message(design["id"], "We need help with customer feedback")
    second = await service.message(design["id"], "Support operators are the users")

    assert first["status"] == "conversation"
    assert first["builder_session_id"] == second["builder_session_id"]
    assert [call["session_id"] for call in client.calls[:2]] == [
        design["builder_session_id"],
        design["builder_session_id"],
    ]
    assert not Path(design["draft_path"]).exists()
    assert "support operators" in second["plan"]

    generated = await service.generate_draft(design["id"])

    assert generated["status"] == "draft_ready"
    assert "app.yaml" in generated["draft_files"]
    assert client.calls[-1]["session_id"] == f"atelier_draft_{design['id']}"


class FakeExperimentClient:
    def __init__(self, store: StudioStore) -> None:
        self.store = store
        self.session_id = ""
        self.calls: list[dict[str, Any]] = []

    async def start_run(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        self.session_id = kwargs["session_id"]
        self.store.append_trace(
            {
                "event": "profile_call.completed",
                "call_id": "call-1",
                "source": "dispatcher",
                "target": "product",
                "source_session_id": self.session_id,
                "target_session_id": "target-session",
                "target_hermes_run_id": "run-product",
                "status": "completed",
            }
        )
        return "run-entry"

    async def events(self, run_id: str):
        yield {"event": "message.delta", "delta": "Evidence PRD-17 from simulated data"}
        yield {"event": "run.completed", "status": "completed"}

    async def status(self, run_id: str) -> dict[str, Any]:
        return {"event": "run.completed", "status": "completed"}


@pytest.mark.asyncio
async def test_experiment_freezes_definition_model_memory_case_and_real_trace(
    tmp_path: Path,
) -> None:
    pack = create_pack(tmp_path / "support")
    case_path = pack / "cases" / "smoke.yaml"
    case_path.write_text(
        """id: smoke
input: check product evidence
memory_policy: clean
assertions:
  calls:
    required: [product]
  output:
    must_contain: [PRD-17]
human_review: Check simulated-data disclosure.
""",
        encoding="utf-8",
    )
    store = StudioStore(tmp_path / ".atelier" / "v2")
    client = FakeExperimentClient(store)
    service = ExperimentService(store, client_factory=lambda *_: client)

    experiment = await service.run(
        pack_root=pack,
        case_path=case_path,
        api_key="runtime-secret",
        runtime_attestation=runtime_attestation(pack, case_path),
        trial_count=2,
    )

    assert experiment["status"] == "completed"
    assert experiment["memory_policy"] == "clean"
    assert experiment["model_fingerprint"] == {
        "provider": "custom",
        "model": "test-model",
    }
    assert experiment["definition_snapshot"]["revision"] == experiment["pack_revision"]
    assert len(experiment["trials"]) == 2
    assert all(trial["assertions_passed"] for trial in experiment["trials"])
    assert all(trial["traces"][0]["target"] == "product" for trial in experiment["trials"])
    assert all("selected clean state" in call["instructions"] for call in client.calls)
    assert all(call["memory_scope"] is None for call in client.calls)
    assert "runtime-secret" not in str(store.get_experiment(experiment["id"]))


@pytest.mark.asyncio
async def test_retained_experiment_propagates_explicit_scope_in_instructions(
    tmp_path: Path,
) -> None:
    pack = create_pack(tmp_path / "support")
    case_path = pack / "cases" / "smoke.yaml"
    case_path.write_text(
        "id: retained\ninput: coach me\nmemory_policy: retained\n"
        "memory_scope: candidate-one\n",
        encoding="utf-8",
    )
    store = StudioStore(tmp_path / ".atelier" / "v2")
    client = FakeExperimentClient(store)

    await ExperimentService(store, client_factory=lambda *_: client).run(
        pack_root=pack,
        case_path=case_path,
        api_key="runtime-secret",
        runtime_attestation=runtime_attestation(pack, case_path),
    )

    assert client.calls[0]["memory_scope"] == "candidate-one"
    assert "'candidate-one'" in client.calls[0]["instructions"]


def test_case_rejects_workflow_and_requires_explicit_retained_scope(tmp_path: Path) -> None:
    case_path = tmp_path / "case.yaml"
    case_path.write_text(
        "id: invalid\ninput: work\nmemory_policy: clean\nsteps: [call-product]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="workflow"):
        load_case(case_path)

    case_path.write_text(
        "id: invalid\ninput: work\nmemory_policy: retained\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="memory_scope"):
        load_case(case_path)


def test_studio_store_rejects_path_traversal_identifiers(tmp_path: Path) -> None:
    root = tmp_path / ".atelier" / "v2"
    store = StudioStore(root)

    with pytest.raises(ValueError, match="Session"):
        store.append_trace(
            {
                "event": "profile_call.started",
                "call_id": "call-1",
                "source_session_id": "../../../outside",
            }
        )
    with pytest.raises(ValueError, match="Session"):
        store.traces("../../../outside")
    with pytest.raises(ValueError, match="Design"):
        store.get_design("../../../outside")
    with pytest.raises(ValueError, match="Experiment"):
        store.get_experiment("../../../outside")

    assert not (tmp_path / "outside.jsonl").exists()


@pytest.mark.asyncio
async def test_experiment_rejects_unattested_runtime_and_candidate_case_changes(
    tmp_path: Path,
) -> None:
    pack = create_pack(tmp_path / "support")
    case_path = pack / "cases" / "smoke.yaml"
    store = StudioStore(tmp_path / ".atelier" / "v2")
    attestation = runtime_attestation(pack, case_path)
    attestation["source_revision"] = "different"

    with pytest.raises(ValueError, match="selected source definition"):
        await ExperimentService(store).run(
            pack_root=pack,
            case_path=case_path,
            api_key="runtime-secret",
            runtime_attestation=attestation,
        )

    attestation = runtime_attestation(pack, case_path)
    with pytest.raises(ValueError, match="changed the Case"):
        await ExperimentService(store).run(
            pack_root=pack,
            case_path=case_path,
            api_key="runtime-secret",
            runtime_attestation=attestation,
            candidate={
                "branch": "candidate",
                "worktree": str(tmp_path),
                "diff_summary": "profile-only change",
                "baseline_pack_revision": "baseline",
                "baseline_case_hash": "different",
            },
        )
