from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from plugin.atelier.schemas import BuildRequest, ReviewRequest, RunRequest
from plugin.atelier.services.apps import AppService
from plugin.atelier.services.builds import BuildService
from plugin.atelier.services.proposals import ProposalService
from plugin.atelier.services.reviews import ReviewService
from plugin.atelier.services.runs import RunService
from plugin.atelier.store import AtelierStore

REVIEW_OUTPUT = """OBSERVATIONS
事实：入口 Agent 调用了专家。
EVIDENCE
事实：Trace 中存在完成的子 Span。
HYPOTHESES
推断：场景说明可以更明确。
PROPOSED_CHANGES
建议：修改场景说明文本。
RISKS
尚缺证据：真实模型输出可能波动。
VALIDATION_PLAN
重放相同场景并比较调用树。
CONFIDENCE
中等。
"""

SCENARIO_PATCH = """diff --git a/apps/sample-app/scenarios/smoke.txt \
b/apps/sample-app/scenarios/smoke.txt
--- a/apps/sample-app/scenarios/smoke.txt
+++ b/apps/sample-app/scenarios/smoke.txt
@@ -1 +1 @@
-before
+after
"""


def _write_generated_app(draft: Path) -> None:
    app = draft / "sample-app"
    for role in ("entry", "expert"):
        profile = app / "profiles" / role
        profile.mkdir(parents=True)
        (profile / "distribution.yaml").write_text(
            f"name: sample-app--{role}\nversion: 1.0.0\n", encoding="utf-8"
        )
    (app / "scenarios").mkdir()
    (app / "scenarios" / "smoke.txt").write_text("before\n", encoding="utf-8")
    (app / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "id": "sample-app",
                "display_name": "Sample App",
                "entry_profile": "sample-app--entry",
                "profiles": [
                    {"name": "sample-app--entry", "source": "profiles/entry"},
                    {"name": "sample-app--expert", "source": "profiles/expert"},
                ],
                "allowed_calls": {"sample-app--entry": ["sample-app--expert"]},
                "scenarios_dir": "scenarios",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (draft / "BUILD.md").write_text("# Build\n\nStatus: AWAITING_APPROVAL\n", encoding="utf-8")


class WorkflowProfiles:
    def __init__(self) -> None:
        self.started: list[str] = []

    def model_environment(self, profile: str) -> dict[str, str]:
        return {}

    def install_app(self, app_dir: Path, definition: Any, *, model_env: dict[str, str]):
        return []

    def start(self, profile: str) -> dict[str, str]:
        self.started.append(profile)
        return {"profile": profile, "status": "healthy"}

    def stop(self, profile: str) -> dict[str, str]:
        return {"profile": profile, "status": "stopped"}

    def restart(self, profile: str, *, terminal_cwd: Path | None = None) -> dict[str, str]:
        return {"profile": profile, "status": "healthy"}

    def endpoint_credentials(self, profile: str) -> tuple[str, str]:
        return f"http://{profile}", "runtime-secret"


class WorkflowHermesClient:
    counter = 0
    runs: dict[str, dict[str, Any]] = {}
    child_callback: Any = None

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url

    async def start_run(self, **kwargs: Any) -> str:
        type(self).counter += 1
        run_id = f"hermes_run_{type(self).counter}"
        type(self).runs[run_id] = {"base_url": self.base_url, **kwargs}
        session_id = str(kwargs.get("session_id") or "")
        task = str(kwargs.get("task") or "")
        if session_id.startswith("atelier_build_"):
            match = re.search(r"Work only in (.+?)\. Read and maintain BUILD\.md", task)
            assert match
            _write_generated_app(Path(match.group(1)))
        elif session_id.startswith("atelier_proposal_"):
            match = re.search(r"candidate\.patch in (.+?)\. The patch paths", task)
            assert match
            (Path(match.group(1)) / "candidate.patch").write_text(
                SCENARIO_PATCH, encoding="utf-8"
            )
        return run_id

    async def events(self, run_id: str):
        run = type(self).runs[run_id]
        session_id = str(run.get("session_id") or "")
        if self.base_url == "http://sample-app--entry" and session_id.endswith("_root"):
            await type(self).child_callback(session_id)
        if self.base_url == "http://atelier-reviewer":
            yield {"event": "message.delta", "delta": REVIEW_OUTPUT, "timestamp": 1}
        else:
            yield {"event": "message.delta", "delta": "处理中", "timestamp": 1}
        yield {"event": "run.completed", "output": "完成", "timestamp": 2}

    async def status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed", "output": "完成"}

    async def stop(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "stopping"}

    async def session_messages(self, session_id: str) -> list[dict[str, str]]:
        return [{"role": "assistant", "content": f"session:{session_id}"}]


async def _wait_for_tasks(service: Any) -> None:
    tasks = list(service._tasks)
    assert tasks
    await asyncio.gather(*tasks)


def _init_git_repository(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "base"], cwd=root, check=True)


async def test_complete_build_review_proposal_and_replay_workflow(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ATELIER_PROJECT_ROOT", str(tmp_path))
    _init_git_repository(tmp_path)
    WorkflowHermesClient.counter = 0
    WorkflowHermesClient.runs = {}

    store = AtelierStore(tmp_path / ".atelier" / "atelier.db")
    profiles = WorkflowProfiles()
    apps = AppService(store)
    builds = BuildService(
        store,
        profiles=profiles,  # type: ignore[arg-type]
        apps=apps,
        client_factory=WorkflowHermesClient,
    )

    build = builds.create(BuildRequest(request="创建一个会按需调用专家的应用"))
    await _wait_for_tasks(builds)
    assert builds.detail(build["id"])["status"] == "awaiting_approval"
    approved = builds.approve(build["id"])
    assert approved["build"]["status"] == "approved"
    assert profiles.started == ["sample-app--entry", "sample-app--expert"]

    subprocess.run(["git", "add", "apps/sample-app"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "generated app"], cwd=tmp_path, check=True)

    runs = RunService(
        store,
        profile_service=profiles,  # type: ignore[arg-type]
        app_service=apps,
        client_factory=WorkflowHermesClient,
    )

    async def call_expert(session_id: str) -> None:
        result = await runs.call(
            {"target": "sample-app--expert", "task": "检查证据"},
            source_profile="sample-app--entry",
            task_id=session_id,
            session_id=session_id,
        )
        assert result["ok"] is True

    WorkflowHermesClient.child_callback = call_expert
    original = runs.start_root(
        RunRequest(app_id="sample-app", input="执行 smoke", scenario_id="smoke")
    )
    await _wait_for_tasks(runs)
    original_detail = runs.detail(original["id"])
    assert original_detail["status"] == "completed"
    assert original_detail["spans"][0]["status"] == "completed"
    assert {event["event_type"] for event in store.list_events(original["id"])} == {
        "message.delta",
        "run.completed",
    }

    store.set_feedback(
        original["id"], outcome="partial", expected_result="说明更明确", feedback="请改进"
    )
    reviews = ReviewService(
        store,
        profiles=profiles,  # type: ignore[arg-type]
        client_factory=WorkflowHermesClient,
    )
    review = reviews.create(
        ReviewRequest(app_id="sample-app", run_ids=[original["id"]], feedback="关注证据")
    )
    await _wait_for_tasks(reviews)
    review_detail = reviews.detail(review["id"])
    assert review_detail["status"] == "completed"
    assert "PROPOSED_CHANGES" in review_detail["result"]

    proposals = ProposalService(
        store,
        profiles=profiles,  # type: ignore[arg-type]
        apps=apps,
        reviews=reviews,
        client_factory=WorkflowHermesClient,
    )
    proposal = proposals.request(review["id"])
    await _wait_for_tasks(proposals)
    assert proposals.detail(proposal["id"])["status"] == "pending"
    applied = proposals.apply(proposal["id"])
    assert applied["proposal"]["status"] == "applied"
    assert (tmp_path / "apps/sample-app/scenarios/smoke.txt").read_text() == "after\n"

    replay = runs.start_root(
        RunRequest(
            app_id=original["app_id"],
            input=original["input_text"],
            scenario_id=original["scenario_id"],
            user_label=f"Replay of {original['id'][:8]}",
        )
    )
    await _wait_for_tasks(runs)
    replay_detail = runs.detail(replay["id"])
    assert replay_detail["status"] == "completed"
    assert replay_detail["spans"][0]["status"] == "completed"
    assert replay_detail["input_text"] == original["input_text"]
    assert replay_detail["scenario_id"] == original["scenario_id"]
