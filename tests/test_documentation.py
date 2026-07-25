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
        "核心路径",
        "安装开发环境",
        "验证与发布一个 Pack",
        "更新语义",
        "四个回归 App Packs",
        "Studio 配置",
        "状态与安全",
        "文档",
        "已知边界",
    }
    for heading in required:
        assert f"## {heading}" in text
    assert "profile_call" in text
    assert "IMPLEMENTATION_HANDOFF.md" in text
    assert "Assurance Lab" in text
    assert "./app update" in text
    assert "docs/MIGRATION_FROM_V1.md" in text


def test_agents_guide_preserves_project_invariants() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = {
        "Atelier 是可删除的开发工坊",
        "`profile_call` 是可选、独立于 Atelier 的应用 Plugin",
        "不修改 Hermes 核心源码",
        "Case 描述输入、状态、Memory Policy、通用结果断言和人工评审提示",
        "真实密钥只能进入 Consumer 拥有、权限为 `0600` 的 Profile `.env`",
        "uv run pytest -q",
        "面向人的 README、`AGENTS.md` 和 `docs/**/*.md` 使用中文说明",
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
