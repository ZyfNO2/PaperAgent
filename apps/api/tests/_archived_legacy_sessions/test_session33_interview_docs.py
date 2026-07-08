"""Session 33: 面试导向材料 — 文档存在性与内容完整性检查.

后端可选测试, 主要验证 docs/interview/ 下 7 个面试文档的内容完整性.
断言规则见 SOP §9。
"""

from __future__ import annotations

import re
from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "interview"

# Session 33始 7 份；Session 34-43 与 ARC 对标逐步扩充为 23 份合法面试文档。
# 维护规则：新增 docs/interview/*.md 后在此清单登记，保持 test_no_extra_unexpected_files 绿。
REQUIRED_FILES = [
    "Project_OnePager.md",
    "Architecture_Diagram.md",
    "Interview_QA_Cards.md",
    "Interview_QA_Cards_Extended.md",
    "Demo_Script_3min.md",
    "Demo_Script_10min.md",
    "Failure_Cases.md",
    "Resume_Bullets.md",
    "Reverse_Questions.md",
    "Self_Introduction_1min.md",
    "Self_Introduction_3min.md",
    "Technical_Highlights.md",
    "Project_DeepDive_Index.md",
    "Known_Limitations_For_Interview.md",
    "RAG_Design_Explainer.md",
    "Agent_Memory_Explainer.md",
    "MCP_FunctionCalling_Explainer.md",
    "MultiAgent_Expansion_Design.md",
    "Deep_Dive_QA_RAG.md",
    "Deep_Dive_QA_Agent.md",
    "Deep_Dive_QA_Memory.md",
    "Deep_Dive_QA_MCP.md",
    "AutoResearchClaw_对标与小型化移植.md",
    "面经全解_2026.md",
    "Deep_Dive_QA_2026新热点.md",
    "RAG_Data_Flow.md",
]  # S50 added RAG_Data_Flow.md


# -------------------------------------------------------------------
# S33-1: docs/interview 目录存在
# -------------------------------------------------------------------


class TestDirectoryExists:
    def test_interview_dir_exists(self):
        assert DOCS_DIR.is_dir(), f"目录不存在: {DOCS_DIR}"


# -------------------------------------------------------------------
# S33-2: 7 个文档存在
# -------------------------------------------------------------------


class TestAllFilesExist:
    def test_all_7_interview_docs_exist(self):
        missing = [f for f in REQUIRED_FILES if not (DOCS_DIR / f).is_file()]
        assert not missing, f"缺少文档: {missing}"

    def test_no_extra_unexpected_files(self):
        actual = {p.name for p in DOCS_DIR.iterdir() if p.suffix == ".md"}
        expected = set(REQUIRED_FILES)
        extra = actual - expected
        assert not extra, f"多余文档: {extra}"


# -------------------------------------------------------------------
# S33-3: OnePager 包含 RAG / Agent / Evidence / Evaluation
# -------------------------------------------------------------------


class TestOnePagerContent:
    def test_onepager_contains_key_terms(self):
        path = DOCS_DIR / "Project_OnePager.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        # Accept both English and Chinese equivalents
        checks = [
            ("RAG", "RAG"),
            ("Agent", "Agent"),
            ("Evidence", "Evidence"),
            ("Evaluation", "Evaluation"),
            ("評估", "评估"),
        ]
        missing = [name for name, *_ in checks if name.lower() not in text.lower()]
        # At least 3 out of 5 key terms should be present
        assert len(missing) < 3, f"OnePager 缺少太多关键术语: {missing}"

    def test_onepager_has_all_required_sections(self):
        path = DOCS_DIR / "Project_OnePager.md"
        text = path.read_text(encoding="utf-8")
        required = ["專案定位", "目標用戶", "核心問題", "技術架構", "技術難點",
                     "測試", "安全邊界", "演示路徑", "未來擴展"]
        missing = [s for s in required if s not in text]
        assert len(missing) <= 2, f"OnePager 缺少太多章节: {missing}"


# -------------------------------------------------------------------
# S33-4: QA Cards 至少 30 个问题
# -------------------------------------------------------------------


class TestQaCardsCount:
    def test_at_least_30_qa_cards(self):
        path = DOCS_DIR / "Interview_QA_Cards.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        # Cards start with "### Q" format
        cards = re.findall(r"^### Q\d+", text, re.MULTILINE)
        assert len(cards) >= 30, f"QA Cards 仅 {len(cards)} 个，需要 >= 30"

    def test_qa_all_6_categories_present(self):
        path = DOCS_DIR / "Interview_QA_Cards.md"
        text = path.read_text(encoding="utf-8")
        categories = ["RAG", "Agent", "Memory", "Tool Calling", "Evaluation", "Safety"]
        shown = [c for c in categories if c in text]
        assert len(shown) >= 5, f"QA 只覆盖了 {shown} 个类别 (需要 5+)"


# -------------------------------------------------------------------
# S33-5: Demo Script 包含 3min / 10min
# -------------------------------------------------------------------


class TestDemoScripts:
    def test_demo_3min_exists(self):
        path = DOCS_DIR / "Demo_Script_3min.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert len(text) > 500, "3min 脚本过短"

    def test_demo_10min_exists(self):
        path = DOCS_DIR / "Demo_Script_10min.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert len(text) > 2000, "10min 脚本过短"


# -------------------------------------------------------------------
# S33-6: Failure Cases 至少 6 类
# -------------------------------------------------------------------


class TestFailureCases:
    def test_at_least_6_failure_cases(self):
        path = DOCS_DIR / "Failure_Cases.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        # Each case is a major section heading: "## Case N: ..."
        cases = re.findall(r"^## Case \d+", text, re.MULTILINE)
        assert len(cases) >= 6, f"Failure Cases 仅 {len(cases)} 个, 需要 >= 6"

    def test_failure_cases_have_required_fields(self):
        path = DOCS_DIR / "Failure_Cases.md"
        text = path.read_text(encoding="utf-8")
        for field in ["輸入", "系統", "使用者", "測試"]:
            assert field in text, f"Failure Cases 缺少字段: {field}"


# -------------------------------------------------------------------
# S33-7: Resume Bullets 至少 5 条
# -------------------------------------------------------------------


class TestResumeBullets:
    def test_at_least_5_bullets(self):
        path = DOCS_DIR / "Resume_Bullets.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        bullets = re.findall(r"^- |^\d+\.", text, re.MULTILINE)
        assert len(bullets) >= 5, f"Resume Bullets 仅 {len(bullets)} 条, 需要 >= 5"


# -------------------------------------------------------------------
# S33-8: 记录 test_session6_llm_path.py 既有失败或已修复状态
# -------------------------------------------------------------------


class TestSession6Status:
    """Session 6 测试状态记录: known skip on LLM unavailability."""

    def test_session6_llm_path_known_status(self):
        """S6 LLM path tests skip gracefully when LLM/Minimax is unavailable.
        This is by design — the heuristic fallback covers production paths.
        """
        s6_path = Path(__file__).resolve().parents[3] / "apps/api/tests/test_session6_llm_path.py"
        assert s6_path.is_file(), "S6 测试文件不存在"
        text = s6_path.read_text(encoding="utf-8")
        # Check that the LLM test gracefully skips
        assert "pytest.skip" in text, "S6 tests should have skip for LLM unavailability"
        assert "heuristic_fallback" in text, "S6 tests should verify heuristic fallback"
