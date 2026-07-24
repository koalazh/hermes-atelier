from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUMAN_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
]
LEGACY_ENGLISH_HEADINGS = {
    "Architecture",
    "Builder and approval",
    "Current evidence",
    "Deletion strategy",
    "Honest limitations",
    "Intent",
    "Kill or pivot",
    "Non-goals",
    "Quick start",
    "Security",
    "Source/runtime split",
    "Stable boundary and Agent autonomy",
    "Trace model",
    "Validation evidence",
    "Why these boundaries",
}


def test_every_human_document_contains_chinese() -> None:
    assert HUMAN_DOCS
    for path in HUMAN_DOCS:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"[\u4e00-\u9fff]", text), f"缺少中文内容：{path.relative_to(ROOT)}"
        headings = {
            match.group(1).strip()
            for match in re.finditer(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE)
        }
        assert not headings & LEGACY_ENGLISH_HEADINGS


def test_readme_covers_user_and_developer_paths() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = {
        "环境要求",
        "快速开始",
        "工作台使用流程",
        "示例应用",
        "常用运维命令",
        "本地数据与清理",
        "开发与验证",
        "故障排查",
        "文档导航",
    }
    for heading in required:
        assert f"## {heading}" in text
    assert "tests/test_full_workflow.py" in text
    assert "scripts/capability_test.py" in text
    assert "AGENTS.md" in text
    assert "(AGENTS.md)" in text


def test_agents_guide_preserves_project_invariants() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = {
        "不得在 Atelier 核心编码业务流程",
        "`atelier_call` 是唯一受 Atelier 观测的跨 Profile 调用边界",
        "不修改 Hermes 核心源码",
        "`.atelier/atelier.db` 是唯一 Atelier 状态事实源",
        "真实密钥只能写入被忽略、权限为 `0600` 的运行态 Profile `.env`",
        "uv run pytest -q tests/test_full_workflow.py",
        "说明性正文与章节标题使用中文",
    }
    for rule in required:
        assert rule in text


def test_local_markdown_links_resolve() -> None:
    for path in HUMAN_DOCS:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.exists(), f"失效链接：{path.relative_to(ROOT)} -> {target}"
