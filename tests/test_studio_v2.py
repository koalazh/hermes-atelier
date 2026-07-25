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
                "Alignment complete.\nDESIGN_STATUS: PLAN_READY\n"
                "=== PLAN.md ===\n# Design Plan\n\nUsers: support operators\n\n"
                "Risk: real API is missing.\n"
                "=== IMPLEMENTATION_HANDOFF.md ===\n# Implementation Handoff\n\n"
                "## Original requirement\nBuild a support application\n\n"
                "## Aligned goal\nHelp support operators.\n\n"
                "## Profile boundaries\nStart with one Profile.\n\n"
                "## Tools, data, and permissions\nThe real API is not connected.\n\n"
                "## Session, Memory, and Skill ownership\nHermes owns Sessions.\n\n"
                "## Recommended collaboration primitive\nNone initially.\n\n"
                "## App Pack and HTTP delivery boundary\nOpenAI-compatible entry.\n\n"
                "## Acceptance Cases\nValidate honest missing-data behavior.\n\n"
                "## Real systems not connected\nSupport API.\n\n"
                "## Explicit non-goals\nNo deployment platform."
            ),
            "Draft generated for inspection.",
        ]

    async def start_run(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if "explicitly selected Generate with Hermes" in kwargs["task"]:
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
    assert "Implementation Handoff" in second["implementation_handoff"]
    assert "Real systems not connected" in second["implementation_handoff"]
    assert Path(second["handoff_path"]).is_file()

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
    assert experiment["memory_policy"] == "new_session"
    assert experiment["model_fingerprint"] == {
        "provider": "custom",
        "model": "test-model",
    }
    assert experiment["definition_snapshot"]["revision"] == experiment["pack_revision"]
    assert len(experiment["trials"]) == 2
    assert all(trial["assertions_passed"] for trial in experiment["trials"])
    assert all(trial["traces"][0]["target"] == "product" for trial in experiment["trials"])
    assert all("selected new_session state" in call["instructions"] for call in client.calls)
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


@pytest.mark.asyncio
async def test_experiment_applies_initial_state_to_trial_instructions(tmp_path: Path) -> None:
    pack = create_pack(tmp_path / "support")
    case_path = pack / "cases" / "smoke.yaml"
    case_path.write_text(
        "id: stateful\ninput: inspect ticket\ninitial_state:\n"
        "  ticket: T-100\nmemory_policy: clean\n",
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

    assert '"ticket": "T-100"' in client.calls[0]["instructions"]


def test_case_schema_rejects_unknown_fields_and_migrates_legacy_terms(
    tmp_path: Path,
) -> None:
    case_path = tmp_path / "case.yaml"
    case_path.write_text(
        "id: invalid\ninput: work\nmemory_policy: clean\nsteps: [call-product]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Extra inputs"):
        load_case(case_path)

    case_path.write_text(
        "id: invalid\ninput: work\nmemory_policy: retained\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="memory_scope"):
        load_case(case_path)

    case_path.write_text(
        "id: migrated\ninput: work\nmemory_policy: clean\ninitial_state:\n  source: old\n",
        encoding="utf-8",
    )
    case, _ = load_case(case_path)
    assert case.memory_policy == "new_session"
    assert case.evaluation_context == {"source": "old"}


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


@pytest.mark.asyncio
async def test_experiment_verifies_candidate_git_identity_and_baseline_case(
    tmp_path: Path,
) -> None:
    import hashlib

    repository = tmp_path / "repository"
    pack = create_pack(repository / "apps" / "support")
    case_path = pack / "cases" / "smoke.yaml"
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-qm", "baseline"], check=True)
    baseline_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    baseline_revision = build_definition_snapshot(AppPack.load(pack))["revision"]
    baseline_case_hash = hashlib.sha256(case_path.read_bytes()).hexdigest()
    subprocess.run(["git", "-C", str(repository), "checkout", "-qb", "candidate"], check=True)
    (pack / "profiles" / "dispatcher" / "SOUL.md").write_text(
        "# candidate dispatcher\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-qm", "candidate"], check=True)
    candidate_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    attestation = runtime_attestation(pack, case_path)
    attestation["source_provenance"] = {"kind": "git", "revision": candidate_commit}
    store = StudioStore(tmp_path / ".atelier" / "v2")
    client = FakeExperimentClient(store)
    candidate = {
        "branch": "candidate",
        "worktree": str(repository),
        "commit": candidate_commit,
        "baseline_commit": baseline_commit,
        "baseline_source_revision": baseline_revision,
        "baseline_case_hash": baseline_case_hash,
    }

    experiment = await ExperimentService(
        store, client_factory=lambda *_: client
    ).run(
        pack_root=pack,
        case_path=case_path,
        api_key="runtime-secret",
        runtime_attestation=attestation,
        candidate=candidate,
    )

    assert experiment["candidate"]["commit"] == candidate_commit
    assert "profiles/dispatcher/SOUL.md" in experiment["candidate"]["diff_summary"]

    invalid = {**candidate, "worktree": str(tmp_path / "missing")}
    with pytest.raises(ValueError, match="worktree"):
        await ExperimentService(store).run(
            pack_root=pack,
            case_path=case_path,
            api_key="runtime-secret",
            runtime_attestation=attestation,
            candidate=invalid,
        )

    case_path.write_text(
        "id: smoke\ninput: changed condition\nmemory_policy: clean\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-qm", "change case"], check=True)
    changed_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    changed_attestation = runtime_attestation(pack, case_path)
    changed_attestation["source_provenance"] = {
        "kind": "git",
        "revision": changed_commit,
    }
    with pytest.raises(ValueError, match="changed the Case"):
        await ExperimentService(store).run(
            pack_root=pack,
            case_path=case_path,
            api_key="runtime-secret",
            runtime_attestation=changed_attestation,
            candidate={**candidate, "commit": changed_commit},
        )

    subprocess.run(
        ["git", "-C", str(repository), "checkout", "-qb", "unrelated", baseline_commit],
        check=True,
    )
    (repository / "UNRELATED.md").write_text("not part of the App Pack\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "UNRELATED.md"], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-qm", "unrelated"], check=True)
    unrelated_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    unrelated_attestation = runtime_attestation(pack, case_path)
    unrelated_attestation["source_provenance"] = {
        "kind": "git",
        "revision": unrelated_commit,
    }

    with pytest.raises(ValueError, match="selected App Pack"):
        await ExperimentService(store).run(
            pack_root=pack,
            case_path=case_path,
            api_key="runtime-secret",
            runtime_attestation=unrelated_attestation,
            candidate={
                **candidate,
                "branch": "unrelated",
                "commit": unrelated_commit,
            },
        )
