from __future__ import annotations

from typing import Any

from scripts import start


def test_dashboard_runs_in_foreground_without_stopping_profiles(monkeypatch) -> None:
    started: list[str] = []
    command: list[str] = []

    class FakeApps:
        def __init__(self, store: Any) -> None:
            pass

        def list(self) -> list[dict[str, str]]:
            return []

    class FakeProfiles:
        def __init__(self, store: Any) -> None:
            pass

        def start(self, profile: str) -> None:
            started.append(profile)

    class FakeProcess:
        def wait(self, *, timeout: float | None = None) -> int:
            return 0

    def start_dashboard(args: list[str], **kwargs: Any) -> FakeProcess:
        command.extend(args)
        return FakeProcess()

    monkeypatch.setattr(start, "AtelierStore", lambda: object())
    monkeypatch.setattr(start, "AppService", FakeApps)
    monkeypatch.setattr(start, "ProfileService", FakeProfiles)
    monkeypatch.setattr(start.subprocess, "Popen", start_dashboard)

    result = start.main(["--dashboard", "--dashboard-port", "9123"])

    assert result == 0
    assert started == ["atelier-builder", "atelier-reviewer"]
    assert command[-6:] == ["dashboard", "--host", "127.0.0.1", "--port", "9123", "--no-open"]


def test_ctrl_c_terminates_dashboard_but_leaves_profiles_running(monkeypatch) -> None:
    started: list[str] = []

    class FakeApps:
        def __init__(self, store: Any) -> None:
            pass

        def list(self) -> list[dict[str, str]]:
            return []

    class FakeProfiles:
        def __init__(self, store: Any) -> None:
            pass

        def start(self, profile: str) -> None:
            started.append(profile)

    class InterruptedProcess:
        terminated = False

        def wait(self, *, timeout: float | None = None) -> int:
            if not self.terminated:
                raise KeyboardInterrupt
            return 0

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            raise AssertionError("graceful termination should not require kill")

    process = InterruptedProcess()
    monkeypatch.setattr(start, "AtelierStore", lambda: object())
    monkeypatch.setattr(start, "AppService", FakeApps)
    monkeypatch.setattr(start, "ProfileService", FakeProfiles)
    monkeypatch.setattr(start.subprocess, "Popen", lambda *args, **kwargs: process)

    result = start.main(["--dashboard"])

    assert result == 130
    assert process.terminated
    assert started == ["atelier-builder", "atelier-reviewer"]
