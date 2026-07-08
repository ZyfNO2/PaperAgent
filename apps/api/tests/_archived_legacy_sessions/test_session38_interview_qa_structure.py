"""Session 38: Interview QA + Demo scripts structural validation (8 个).

S38-1: QA Cards 总数 >= 60
S38-2: 每张卡包含 project_evidence
S38-3: Demo 3min 字数 <= 900
S38-4: Demo 10min 有步骤编号
S38-5: Deep Dive 覆盖 RAG/Agent/Memory/MCP
S38-6: 每个文档至少引用一个项目文件
S38-7: 文档包含"当前不足"
S38-8: 不出现夸大承诺
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "interview"


def _count_qa_cards() -> int:
    """统计所有 Interview_QA_Cards*.md 中的 Q 卡片数."""
    total = 0
    for f in sorted(DOCS.glob("Interview_QA_Cards*.md")):
        text = f.read_text(encoding="utf-8")
        # Q 卡片标记: Q31., Q1., ### Q1
        matches = re.findall(r"^##\s*Q\d+\.", text, re.MULTILINE)
        # 也支持 ### Q1 格式 (S33 老格式)
        matches2 = re.findall(r"^###\s*Q\d+", text, re.MULTILINE)
        total += max(len(matches), len(matches2))
    return total


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S38-1: QA Cards 总数 >= 60
# ---------------------------------------------------------------------------


class TestQACardCount:
    def test_total_cards_at_least_60(self):
        n = _count_qa_cards()
        assert n >= 60, f"only {n} QA cards found, need >= 60"


# ---------------------------------------------------------------------------
# S38-2: 每张卡包含 project_evidence
# ---------------------------------------------------------------------------


class TestCardsHaveEvidence:
    def test_each_card_in_extended_has_evidence(self):
        text = _read("Interview_QA_Cards_Extended.md")
        # 检查每个 Q 块都有 "项目证据" 或 "project_evidence"
        q_blocks = re.split(r"\n##\s*Q\d+\.", text)
        for blk in q_blocks[1:]:  # 跳过 preamble
            assert "项目证据" in blk or "project_evidence" in blk, (
                f"card block missing evidence: {blk[:80]}"
            )


# ---------------------------------------------------------------------------
# S38-3: Demo 3min 字数 <= 900
# ---------------------------------------------------------------------------


class TestDemo3Min:
    def test_demo_3min_word_count(self):
        text = _read("Demo_Script_3min.md")
        # 用中文字符数 (CJK 字符)
        cjk = re.findall(r"[一-鿿]", text)
        total_cjk = len(cjk)
        # SOP 说 <= 900 字 (这里按 CJK 字符计)
        assert total_cjk <= 900, f"Demo 3min too long: {total_cjk} CJK chars (max 900)"


# ---------------------------------------------------------------------------
# S38-4: Demo 10min 有步骤编号
# ---------------------------------------------------------------------------


class TestDemo10Min:
    def test_demo_10min_has_steps(self):
        text = _read("Demo_Script_10min.md")
        # 步骤 1, 步骤 2, or Step 1, Step 2
        has_step_marker = bool(
            re.search(r"(?:步骤\s*\d|Step\s*\d|^\s*\d+\.\s)", text, re.MULTILINE)
        )
        assert has_step_marker, "Demo 10min should have step numbering"


# ---------------------------------------------------------------------------
# S38-5: Deep Dive 覆盖 RAG/Agent/Memory/MCP
# ---------------------------------------------------------------------------


class TestDeepDiveCoverage:
    @pytest.mark.parametrize("name", [
        "Deep_Dive_QA_RAG.md",
        "Deep_Dive_QA_Agent.md",
        "Deep_Dive_QA_Memory.md",
        "Deep_Dive_QA_MCP.md",
    ])
    def test_deep_dive_doc_exists(self, name):
        path = DOCS / name
        assert path.exists(), f"{name} missing"

    def test_each_deep_dive_has_15plus_qa(self):
        for name in ("Deep_Dive_QA_RAG.md", "Deep_Dive_QA_Agent.md",
                     "Deep_Dive_QA_Memory.md", "Deep_Dive_QA_MCP.md"):
            text = _read(name)
            qs = re.findall(r"^##\s*Q\d+", text, re.MULTILINE)
            assert len(qs) >= 15, f"{name} only has {len(qs)} Q cards, need >= 15"


# ---------------------------------------------------------------------------
# S38-6: 每个文档至少引用一个项目文件
# ---------------------------------------------------------------------------


class TestEachDocCitesFile:
    @pytest.mark.parametrize("name", [
        "Interview_QA_Cards.md",
        "Interview_QA_Cards_Extended.md",
        "Deep_Dive_QA_RAG.md",
        "Deep_Dive_QA_Agent.md",
        "Deep_Dive_QA_Memory.md",
        "Deep_Dive_QA_MCP.md",
        "Demo_Script_3min.md",
        "Demo_Script_10min.md",
    ])
    def test_doc_cites_a_file(self, name):
        text = _read(name)
        # 检查 apps/ 或 docs/ 路径引用 (允许 backtick / bash 命令 / 表格)
        has_file_ref = bool(
            re.search(r"apps/[\w/]+\.py", text)
            or re.search(r"apps/web/[\w/]+\.[a-z]+", text)
            or re.search(r"docs/[\w/]+\.md", text)
        )
        assert has_file_ref, f"{name} should reference at least one project file"


# ---------------------------------------------------------------------------
# S38-7: 文档包含"当前不足"
# ---------------------------------------------------------------------------


class TestBoundaryAndLimitation:
    @pytest.mark.parametrize("name", [
        "Deep_Dive_QA_RAG.md",
        "Deep_Dive_QA_Agent.md",
        "Deep_Dive_QA_Memory.md",
        "Deep_Dive_QA_MCP.md",
        "Interview_QA_Cards_Extended.md",
    ])
    def test_doc_mentions_limitations(self, name):
        text = _read(name)
        has_boundary = (
            "边界" in text
            or "诚实回答" in text
            or "Mock" in text
            or "未来" in text
            or "不足" in text
            or "局限" in text
            or "boundary" in text.lower()
            or "limitation" in text.lower()
        )
        assert has_boundary, f"{name} should mention limitations/boundaries"


# ---------------------------------------------------------------------------
# S38-8: 不出现夸大承诺
# ---------------------------------------------------------------------------


class TestNoOverpromise:
    @pytest.mark.parametrize("name", [
        "Interview_QA_Cards.md",
        "Interview_QA_Cards_Extended.md",
        "Deep_Dive_QA_RAG.md",
        "Deep_Dive_QA_Agent.md",
        "Deep_Dive_QA_Memory.md",
        "Deep_Dive_QA_MCP.md",
        "Demo_Script_3min.md",
        "Demo_Script_10min.md",
        "Project_OnePager.md",
    ])
    def test_no_overpromise_phrases(self, name):
        text = _read(name)
        # 禁止的夸张词
        forbidden = [
            "完美", "100% 准确", "100%准确", "无幻觉", "零失败",
            "完美解决", "万能", "industry-leading", "世界领先",
            "完美无缺", "完美支持", "毫无问题",
        ]
        for word in forbidden:
            assert word not in text, f"{name} contains overpromise phrase: '{word}'"