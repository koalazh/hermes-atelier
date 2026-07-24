from pathlib import Path

import pytest

from plugin.atelier.paths import ensure_within


def test_ensure_within_accepts_child(tmp_path: Path) -> None:
    child = tmp_path / "apps" / "one"
    child.mkdir(parents=True)
    assert ensure_within(child, tmp_path / "apps") == child.resolve()


def test_ensure_within_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "apps"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        ensure_within(tmp_path / "other", root)


def test_ensure_within_rejects_root_by_default(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="below"):
        ensure_within(tmp_path, tmp_path)
