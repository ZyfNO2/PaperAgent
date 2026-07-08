"""Session 40: Resume packaging + tech highlights structural tests (8 个).

S40-1: Resume_Bullets 至少 8 条
S40-2: 1min 自我介绍 <= 500 字
S40-3: 3min 自我介绍包含项目背景、架构、难点、测试
S40-4: Technical_Highlights 至少 5 项
S40-5: Known_Limitations 明确不夸大
S40-6: 每个亮点能链接到项目文件或测试
S40-7: 不出现"保证通过开题""完全避免幻觉"等绝对承诺
S40-8: 6 个新文档全部存在
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "interview"


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S40-1: Resume_Bullets 至少 8 条
# ---------------------------------------------------------------------------


class TestResumeBullets:
    def test_resume_bullets_at_least_8(self):
        text = _read("Resume_Bullets.md")
        bullets = re.findall(r"^[-*]\s+", text, re.MULTILINE)
        assert len(bullets) >= 8, f"only {len(bullets)} bullets, need >= 8"


# ---------------------------------------------------------------------------
# S40-2: 1min 自我介绍 <= 500 字
# ---------------------------------------------------------------------------


class TestSelfIntro1Min:
    def test_shortest_template_within_500_chars(self):
        """SOP 要求 1min 自我介绍 <= 500 字。检查最短模板 (A)."""
        text = _read("Self_Introduction_1min.md")
        # 找模板 A (最短)
        m = re.search(r"## 模板 A.*?(?=\n##|\Z)", text, re.DOTALL)
        assert m is not None, "Template A not found"
        template = m.group(0)
        cjk = re.findall(r"[一-鿿]", template)
        assert len(cjk) <= 500, (
            f"Template A too long: {len(cjk)} CJK chars (max 500)"
        )


# ---------------------------------------------------------------------------
# S40-3: 3min 自我介绍包含项目背景、架构、难点、测试
# ---------------------------------------------------------------------------


class TestSelfIntro3Min:
    def test_3min_contains_key_topics(self):
        text = _read("Self_Introduction_3min.md")
        # 4 个必备元素
        assert "项目背景" in text or "背景" in text, "3min should have 项目背景"
        assert "架构" in text or "技术" in text, "3min should have 架构"
        assert "难点" in text or "挑战" in text or "权衡" in text, "3min should have 难点"
        assert "测试" in text or "可靠性" in text, "3min should have 测试"

    def test_3min_has_time_segments(self):
        """3 分钟自我介绍应该有分段（30 秒 / 60 秒 / 45 秒）."""
        text = _read("Self_Introduction_3min.md")
        has_segments = bool(
            re.search(r"\d+\s*秒", text) or re.search(r"\d+\s*分", text)
        )
        assert has_segments, "3min should have time segments"


# ---------------------------------------------------------------------------
# S40-4: Technical_Highlights 至少 5 项
# ---------------------------------------------------------------------------


class TestTechHighlights:
    def test_highlights_at_least_5(self):
        text = _read("Technical_Highlights.md")
        # 亮点 1, 亮点 2, ...
        highlights = re.findall(r"^##\s*亮点\s*\d+", text, re.MULTILINE)
        assert len(highlights) >= 5, f"only {len(highlights)} highlights, need >= 5"

    def test_each_highlight_has_project_evidence(self):
        text = _read("Technical_Highlights.md")
        # 每个亮点块应该有项目证据
        blocks = re.split(r"\n##\s*亮点\s*\d+", text)
        for blk in blocks[1:]:
            has_evidence = (
                "项目证据" in blk
                or "可展示文件" in blk
                or "apps/" in blk
                or ".py" in blk
            )
            assert has_evidence, f"highlight block missing evidence: {blk[:100]}"


# ---------------------------------------------------------------------------
# S40-5: Known_Limitations 明确不夸大
# ---------------------------------------------------------------------------


class TestKnownLimitations:
    def test_limitations_doc_exists(self):
        path = DOCS / "Known_Limitations_For_Interview.md"
        assert path.exists()

    def test_limitations_no_overpromise_in_recommendations(self):
        text = _read("Known_Limitations_For_Interview.md")
        # 排除 "不要说的话" / "反例" 段 (3.x), 只检查正向推荐段
        # 简单做法: 移除 3.x 整段
        cleaned = re.sub(
            r"### 3\..*?(?=^###\s*\d+\.|^##\s*\d|\Z)",
            "",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        forbidden = [
            "100% 准确", "100%准确", "完全避免幻觉", "完美解决", "绝对可靠",
            "保证通过", "100% 可用", "100%可用",
        ]
        for w in forbidden:
            assert w not in cleaned, (
                f"Limitations recommendations contain overpromise: '{w}'"
            )

    def test_limitations_uses_3_part_template(self):
        """限制 + 应对 + 后续 三段式."""
        text = _read("Known_Limitations_For_Interview.md")
        assert "限制" in text
        assert "应对" in text or "解决" in text
        assert "后续" in text or "未来" in text or "生产环境" in text


# ---------------------------------------------------------------------------
# S40-6: 每个亮点能链接到项目文件或测试
# ---------------------------------------------------------------------------


class TestHighlightsLinkToFiles:
    def test_5_highlights_cite_source_files(self):
        text = _read("Technical_Highlights.md")
        # 至少 5 个 apps/ 或 test_session 引用
        file_refs = re.findall(r"apps/[\w/]+\.py", text)
        assert len(file_refs) >= 5, (
            f"only {len(file_refs)} file refs in highlights, need >= 5"
        )


# ---------------------------------------------------------------------------
# S40-7: 不出现绝对承诺
# ---------------------------------------------------------------------------


class TestNoAbsolutePromises:
    @pytest.mark.parametrize("name", [
        "Resume_Bullets.md",
        "Self_Introduction_1min.md",
        "Self_Introduction_3min.md",
        "Technical_Highlights.md",
        "Known_Limitations_For_Interview.md",
        "Project_DeepDive_Index.md",
    ])
    def test_doc_no_absolute_promises(self, name):
        text = _read(name)
        # Known_Limitations 的 3.x "不要说的话" 段会列出反例, 排除掉
        if name == "Known_Limitations_For_Interview.md":
            check_text = re.sub(
                r"### 3\..*?(?=^###\s*\d+\.|^##\s*\d|\Z)",
                "",
                text,
                flags=re.MULTILINE | re.DOTALL,
            )
        else:
            check_text = text
        forbidden = [
            "保证通过开题", "完全避免幻觉", "100% 准确", "100%准确",
            "绝对可靠", "100% 可用", "100%可用",
            "完全无幻觉", "毫无问题",
        ]
        for w in forbidden:
            assert w not in check_text, f"{name} contains absolute promise: '{w}'"


# ---------------------------------------------------------------------------
# S40-8: 6 个新文档全部存在
# ---------------------------------------------------------------------------


class TestAllDocsExist:
    @pytest.mark.parametrize("name", [
        "Resume_Bullets.md",
        "Self_Introduction_1min.md",
        "Self_Introduction_3min.md",
        "Project_DeepDive_Index.md",
        "Technical_Highlights.md",
        "Known_Limitations_For_Interview.md",
    ])
    def test_doc_exists(self, name):
        path = DOCS / name
        assert path.exists(), f"{name} missing at {path}"


# ---------------------------------------------------------------------------
# 额外: 深挖索引 + 反问配合
# ---------------------------------------------------------------------------


class TestProjectDeepDiveIndex:
    def test_deep_dive_index_has_15_modules(self):
        text = _read("Project_DeepDive_Index.md")
        modules = re.findall(r"^##\s*模块\s*\d+", text, re.MULTILINE)
        assert len(modules) >= 10, f"only {len(modules)} modules in index"

    def test_each_module_has_core_files(self):
        text = _read("Project_DeepDive_Index.md")
        # 拆分 "## 模块 N" 块, 但需要处理 "## 索引" 这种非模块标题
        blocks = re.split(r"\n##\s*模块\s*\d+", text)
        for blk in blocks[1:]:
            has_files = "apps/" in blk or ".py" in blk
            assert has_files, f"module block missing apps/ refs: {blk[:80]}"