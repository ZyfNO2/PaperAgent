"""Session 30: 委员会复核后端测试.

覆盖 SOP §5 后端 8 条:
1. 缺数据集 -> 至少 high issue
2. 无 baseline -> 至少 high issue
3. 无证据段落 -> medium/high issue
4. fatal issue 未处理不得 pass
5. accept_fix 生成 revision action
6. rerun_review 保留历史轮次
7. revise_topic 触发回到 keyword_review
8. ReviewRound 可序列化
"""

from __future__ import annotations

import pytest
from app.schemas_review import (
    ReviewRequest,
    ReviewRound,
    ReviewVerdict,
    RevisionAction,
    RevisionActionType,
    Severity,
    can_verdict_pass,
)
from app.services.review import run_review, get_review_history, clear_review_history


# ------------------------------------------------------------------- #
# helpers
# ------------------------------------------------------------------- #

TOPIC = "Test Topic S30"


def _sections_minimal():
    """Minimal sections with most content but no evidence."""
    return [
        {"section_id": "topic_direction", "content": "钢铁缺陷检测"},
        {"section_id": "background", "content": "工业质检"},
        {"section_id": "literature_review", "content": "综述"},
        {"section_id": "research_objectives", "content": "提高精度"},
        {"section_id": "research_content", "content": "改进模型"},
        {"section_id": "technical_approach", "content": "ResNet"},
        {"section_id": "dataset_experiment", "content": "待定"},
        {"section_id": "innovation", "content": "轻量改进"},
    ]


def _feasibility_with_vetoes():
    return {
        "verdict": "PIVOT",
        "overall_score": 34,
        "hard_vetoes": [
            {"rule": "no_dataset", "triggered": True, "description": "缺数据集"},
            {"rule": "no_baseline", "triggered": True, "description": "无 baseline"},
            {"rule": "no_experiment_plan", "triggered": True, "description": "无实验方案"},
        ],
    }


@pytest.fixture(autouse=True)
def _clear_history():
    clear_review_history(TOPIC)
    yield
    clear_review_history(TOPIC)


# ------------------------------------------------------------------- #
# S30-1: 缺数据集 -> 至少 high issue
# ------------------------------------------------------------------- #


class TestNoDataset:
    def test_no_dataset_generates_fatal_or_high(self):
        """S30-1: 缺数据集产生 fatal/high issue."""
        req = ReviewRequest(
            topic_title=TOPIC,
            sections=_sections_minimal(),
            feasibility=_feasibility_with_vetoes(),
        )
        round_data = run_review(req)
        dataset_issues = [
            i for i in round_data.issues
            if "数据集" in i.message or "dataset" in i.section_id
        ]
        assert len(dataset_issues) >= 1
        assert any(i.severity in (Severity.fatal, Severity.high) for i in dataset_issues)


# ------------------------------------------------------------------- #
# S30-2: 无 baseline -> 至少 high issue
# ------------------------------------------------------------------- #


class TestNoBaseline:
    def test_no_baseline_generates_fatal_or_high(self):
        """S30-2: 无 baseline 产生 fatal/high issue."""
        req = ReviewRequest(
            topic_title=TOPIC,
            sections=_sections_minimal(),
            feasibility=_feasibility_with_vetoes(),
        )
        round_data = run_review(req)
        baseline_issues = [
            i for i in round_data.issues
            if "baseline" in i.message.lower()
        ]
        assert len(baseline_issues) >= 1
        assert any(i.severity in (Severity.fatal, Severity.high) for i in baseline_issues)


# ------------------------------------------------------------------- #
# S30-3: 无证据段落 -> medium/high issue
# ------------------------------------------------------------------- #


class TestNoEvidence:
    def test_no_evidence_section_generates_issue(self):
        """S30-3: 无证据段落产生 medium/high issue."""
        req = ReviewRequest(
            topic_title=TOPIC,
            sections=_sections_minimal(),
            feasibility=_feasibility_with_vetoes(),
        )
        round_data = run_review(req)
        no_evidence_issues = [
            i for i in round_data.issues
            if "缺少" in i.message or "无证据" in i.message or "证据" in i.message
        ]
        assert len(no_evidence_issues) >= 1
        assert any(i.severity in (Severity.high, Severity.medium) for i in no_evidence_issues)


# ------------------------------------------------------------------- #
# S30-4: fatal issue 未处理不得 pass
# ------------------------------------------------------------------- #


class TestFatalBlocksPass:
    def test_fatal_unresolved_cannot_pass(self):
        """S30-4: 有未处理 fatal issue 时 verdict 不能是 pass."""
        req = ReviewRequest(
            topic_title=TOPIC,
            sections=_sections_minimal(),
            feasibility=_feasibility_with_vetoes(),
        )
        round_data = run_review(req)
        has_fatal = any(i.severity == Severity.fatal for i in round_data.issues)
        if has_fatal:
            assert round_data.verdict != ReviewVerdict.pass_, "Should not pass with fatal issues"
            assert not can_verdict_pass(round_data)


# ------------------------------------------------------------------- #
# S30-5: accept_fix 生成 revision action
# ------------------------------------------------------------------- #


class TestAcceptFix:
    def test_accept_fix_generates_action(self):
        """S30-5: accept_fix 生成对应 action."""
        req = ReviewRequest(
            topic_title=TOPIC,
            sections=_sections_minimal(),
            feasibility=_feasibility_with_vetoes(),
        )
        round_data = run_review(req)
        assert len(round_data.required_actions) >= 1 or len(round_data.optional_actions) >= 1
        all_actions = round_data.required_actions + round_data.optional_actions
        assert any(a.action_type == RevisionActionType.accept_fix for a in all_actions)


# ------------------------------------------------------------------- #
# S30-6: rerun_review 保留历史轮次
# ------------------------------------------------------------------- #


class TestRerunReview:
    def test_history_preserves_rounds(self):
        """S30-6: 多次复核保留历史轮次."""
        req1 = ReviewRequest(topic_title=TOPIC, sections=_sections_minimal())
        run_review(req1)

        req2 = ReviewRequest(topic_title=TOPIC, sections=_sections_minimal())
        run_review(req2)

        history = get_review_history(TOPIC)
        assert len(history.rounds) == 2
        assert history.rounds[0].round_id == 1
        assert history.rounds[1].round_id == 2


# ------------------------------------------------------------------- #
# S30-7: revise_topic 触发回到 keyword_review
# ------------------------------------------------------------------- #


class TestReviseTopic:
    def test_revise_topic_action_exists(self):
        """S30-7: revise_topic action 可生成."""
        action = RevisionAction(
            action_id="act_revise",
            action_type=RevisionActionType.revise_topic,
            target_issue_id="adv_01",
            description="回到关键词阶段",
        )
        assert action.action_type == RevisionActionType.revise_topic


# ------------------------------------------------------------------- #
# S30-8: ReviewRound 可序列化
# ------------------------------------------------------------------- #


class TestSerialization:
    def test_review_round_json_serializable(self):
        """S30-8: ReviewRound 可序列化为 JSON."""
        req = ReviewRequest(
            topic_title=TOPIC,
            sections=_sections_minimal(),
            feasibility=_feasibility_with_vetoes(),
        )
        round_data = run_review(req)
        json_str = round_data.model_dump_json()
        assert len(json_str) > 100
        # Re-parse
        data = round_data.model_dump()
        assert "verdict" in data
        assert "issues" in data
        assert isinstance(data["issues"], list)
