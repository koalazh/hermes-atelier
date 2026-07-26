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
        "先理解完整链路",
        "我应该从哪里开始",
        "你最终会得到什么",
        "最短日常工作流",
        "Core 与 Assurance Lab",
        "四个可以参考的 App Packs",
        "按任务查文档",
        "当前不提供什么",
    }
    for heading in required:
        assert f"## {heading}" in text
    assert "profile_call" in text
    assert "IMPLEMENTATION_HANDOFF.md" in text
    assert "Assurance Lab" in text
    assert "docs/GETTING_STARTED.md" in text
    assert "docs/MIGRATION_FROM_V1.md" in text


def test_getting_started_covers_one_complete_user_journey() -> None:
    text = (ROOT / "docs" / "GETTING_STARTED.md").read_text(encoding="utf-8")
    required = {
        "完成后的样子",
        "路径 A：先跑通一个已存在的 App Pack",
        "路径 B：从自己的业务需求创建应用",
        "阶段 1：安装 Atelier UI 和 Builder",
        "阶段 2：用 Builder 对齐需求并导出 handoff",
        "阶段 3：交给 Coding Agent 实现",
        "阶段 4：验证并生成 App Pack release",
        "阶段 5：由 Consumer 用 Hermes 安装和运行",
        "阶段 6：交付 HTTP 使用方式",
        "怎样查看运行和协作证据",
        "什么时候才需要 Assurance Lab",
        "常见卡点",
    }
    for heading in required:
        assert f"## {heading}" in text or f"### {heading}" in text
    for command in (
        "uv run atelier validate",
        "uv run atelier release",
        "hermes -p default profile install",
        "hermes -p atelier-builder gateway start",
        "./app install",
        "./app configure",
        "./app start",
        "/v1/chat/completions",
    ):
        assert command in text


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
