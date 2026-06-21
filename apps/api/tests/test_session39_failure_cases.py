"""Session 39: Failure cases + reverse questions structural tests (8 个).

S39-1: Failure_Cases >= 10 个案例
S39-2: 每个 case 有 system_block
S39-3: 每个 case 有 related_tests
S39-4: 包含至少 1 个真实历史失败
S39-5: 反问 >= 8
S39-6: 反问文件存在
S39-7: 不把失败写成缺点逃避
S39-8: 工程边界有应对措施
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
# S39-1: Failure_Cases >= 10
# ---------------------------------------------------------------------------


class TestFailureCaseCount:
    def test_failure_cases_at_least_10(self):
        text = _read("Failure_Cases.md")
        # 兼容 "Case 1" 和 "案例 1" 两种格式
        cases = re.findall(r"(?:^|\n)#{2,3}\s*(?:Case|案例)\s*\d+", text)
        assert len(cases) >= 10, f"only {len(cases)} cases found, need >= 10"

    def test_failure_cases_table_mentions_all(self):
        text = _read("Failure_Cases.md")
        # 案例對照表部分
        assert "案例對照表" in text or "案例对照表" in text


# ---------------------------------------------------------------------------
# S39-2: 每个 case 有 system_block
# ---------------------------------------------------------------------------


class TestCasesHaveSystemBlock:
    def test_each_case_mentions_blocking(self):
        text = _read("Failure_Cases.md")
        # 拆分 case 块
        cases = re.split(r"\n#{2,3}\s*(?:Case|案例)\s*\d+", text)
        for blk in cases[1:]:
            # 检查是否提到拦截/触发/维度等关键字
            has_block = (
                "系統如何攔截" in blk
                or "系统如何拦截" in blk
                or "系統攔截" in blk
                or "攔截" in blk
                or "拦截" in blk
                or "block" in blk.lower()
            )
            assert has_block, f"case block missing system_block: {blk[:100]}"


# ---------------------------------------------------------------------------
# S39-3: 每个 case 有 related_tests
# ---------------------------------------------------------------------------


class TestCasesHaveRelatedTests:
    def test_each_case_mentions_tests(self):
        text = _read("Failure_Cases.md")
        cases = re.split(r"\n#{2,3}\s*(?:Case|案例)\s*\d+", text)
        for blk in cases[1:]:
            has_test = (
                "對應測試" in blk
                or "对应测试" in blk
                or "test_session" in blk
                or "test_one_topic" in blk
            )
            assert has_test, f"case block missing related_tests: {blk[:100]}"


# ---------------------------------------------------------------------------
# S39-4: 包含至少 1 个真实历史失败
# ---------------------------------------------------------------------------


class TestRealHistoricalFailure:
    def test_real_historical_failure_mentioned(self):
        text = _read("Failure_Cases.md")
        # SOP 提到 S31 中既有 test_session6_llm_path.py 失败
        # 实际历史: S30 评审发现 S32 readiness page 不可见
        has_historical = (
            "test_session6_llm_path" in text
            or "test_one_topic_session32_readiness" in text
            or "S30" in text
            or "歷史" in text
            or "历史" in text
        )
        assert has_historical


# ---------------------------------------------------------------------------
# S39-5: 反问 >= 8
# ---------------------------------------------------------------------------


class TestReverseQuestions:
    def test_reverse_questions_at_least_8(self):
        text = _read("Reverse_Questions.md")
        # 反问 1, 反问 2, ...
        questions = re.findall(r"^##\s*反问\s*\d+", text, re.MULTILINE)
        assert len(questions) >= 8, f"only {len(questions)} reverse questions, need >= 8"


# ---------------------------------------------------------------------------
# S39-6: 反问文件存在
# ---------------------------------------------------------------------------


class TestReverseQuestionsDocExists:
    def test_doc_exists(self):
        path = DOCS / "Reverse_Questions.md"
        assert path.exists(), f"Reverse_Questions.md missing at {path}"


# ---------------------------------------------------------------------------
# S39-7: 不把失败写成缺点逃避
# ---------------------------------------------------------------------------


class TestFailureNotExcusingSelf:
    def test_no_self_deprecation_phrases(self):
        text = _read("Failure_Cases.md")
        forbidden = [
            "完全失败", "毫无价值", "彻底崩溃", "毫无意义",
            "彻底失败", "完全崩溃", "无法挽救",
        ]
        for w in forbidden:
            assert w not in text, f"Failure_Cases contains self-deprecation: '{w}'"

    def test_each_case_has_solution(self):
        """每个 case 都应该包含应对 / 改进 / 工程边界 等正向描述."""
        text = _read("Failure_Cases.md")
        cases = re.split(r"\n#{2,3}\s*(?:Case|案例)\s*\d+", text)
        for blk in cases[1:]:
            has_solution = (
                "面試怎麼解釋" in blk
                or "面试怎么解释" in blk
                or "工程" in blk
                or "攔截" in blk
                or "拦截" in blk
                or "fallback" in blk.lower()
                or "降級" in blk
                or "降级" in blk
                or "恢復" in blk
                or "恢复" in blk
            )
            assert has_solution, f"case block missing solution context: {blk[:100]}"


# ---------------------------------------------------------------------------
# S39-8: 工程边界有应对措施
# ---------------------------------------------------------------------------


class TestEngineeringBoundaries:
    def test_references_session_32_36_37(self):
        """应该覆盖 S32 (readiness) / S36 (MCP) / S37 (multi-agent) 的失败案例."""
        text = _read("Failure_Cases.md")
        # 至少提到 3 个 session 范围
        sessions_mentioned = 0
        for s in ("session32", "session35", "session36", "session37", "session34"):
            if s in text:
                sessions_mentioned += 1
        assert sessions_mentioned >= 3, (
            f"only {sessions_mentioned} S32-S37 sessions mentioned, need >= 3"
        )

    def test_failure_cases_cite_source_files(self):
        """失败案例应该引用项目测试文件."""
        text = _read("Failure_Cases.md")
        has_refs = bool(
            re.search(r"test_session\d+_\w+\.py", text)
            or re.search(r"test_one_topic_session\d+_\w+\.py", text)
        )
        assert has_refs, "Failure_Cases should reference session test files"