"""Phase 02 Pydantic model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.agents.nodes.phase2_decompose import (
    allow_proceed_to_phase03,
    decompose_heuristic,
)
from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


def _make_intake(rating: str = "A") -> ProjectIntake:
    return ProjectIntake.model_validate(
        {
            "case_id": f"P2_TEST_{rating}",
            "major": "计算机科学与技术",
            "degree_type": "硕士",
            "goal_level": "保毕业",
            "thesis_deadline": "2027-06-01",
            "proposal_deadline": "2026-10-15",
            "first_result_deadline": "2026-12-31",
            "advisor_direction": "图神经网络",
            "school_requirements": ["中文文献"],
            "inherited_resources": [
                InheritedResource(kind="同门毕业论文", description="x", available=True)
            ],
            "student_resources": StudentResourceProfile(
                programming_level="熟练",
                compute_resource="笔记本 3060",
                weekly_hours=25,
            ),
            "raw_topic": "基于图神经网络的学术论文推荐方法研究",
            "must_keep": ["图神经网络"],
            "intake_rating": rating,
        }
    )


def test_heuristic_produces_complete_topicspec() -> None:
    spec = decompose_heuristic(_make_intake())
    assert spec.raw_topic
    assert spec.normalized_topic
    # normalized_topic 应当是 raw_topic 的收缩或相同；启发式不扩大承诺
    assert spec.normalized_topic.strip() != ""
    assert len(spec.work_package_drafts) >= 2
    assert spec.thesis_mapping.chapter_3_wp1
    assert spec.thesis_mapping.chapter_4_wp2
    assert spec.evaluation_metrics


def test_heuristic_normalizes_short_topic() -> None:
    intake = _make_intake()
    intake = intake.model_copy(
        update={"raw_topic": "GNN 论文推荐"}
    )
    spec = decompose_heuristic(intake)
    # 启发式应当在短题目上加"方法研究"后缀
    assert "方法研究" in spec.normalized_topic
    assert spec.normalized_topic != intake.raw_topic


def test_heuristic_allow_proceed_to_phase03() -> None:
    spec = decompose_heuristic(_make_intake())
    allow, reason = allow_proceed_to_phase03(spec)
    assert allow is True, reason


def test_risk_term_detection() -> None:
    intake = _make_intake()
    intake = intake.model_copy(
        update={"raw_topic": "基于大模型的通用智能实时高精度开题助手"}
    )
    spec = decompose_heuristic(intake)
    risk_terms = {r.term for r in spec.risk_terms}
    # 应当至少识别 大模型 / 通用 / 实时 / 高精度 / 智能
    assert "大模型" in risk_terms
    assert "通用" in risk_terms
    assert "实时" in risk_terms
    assert "高精度" in risk_terms
    assert "智能" in risk_terms


def test_heuristic_fallback_rating_B_for_too_many_risks() -> None:
    intake = _make_intake()
    intake = intake.model_copy(
        update={"raw_topic": "基于大模型的通用智能实时高精度全自动化开题助手"}
    )
    spec = decompose_heuristic(intake)
    # ≥4 个风险词 → B
    assert spec.decomposition_rating == "B"


def test_topicspec_rejects_empty_work_packages() -> None:
    from packages.domain.phase2_models import (
        TopicSpec,
        ThesisMapping,
    )
    with pytest.raises(ValidationError):
        TopicSpec(
            project_id="1",
            source_intake_case_id="x",
            goal_level="保毕业",
            raw_topic="t",
            normalized_topic="t",
            thesis_mapping=ThesisMapping(
                chapter_1_intro="a", chapter_2_basics="b",
                chapter_3_wp1="c", chapter_4_wp2="d", chapter_5_summary="e",
            ),
            work_package_drafts=[],
        )
