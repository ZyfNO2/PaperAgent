"""Phase 07 Pydantic + proposal + committee tests."""

from __future__ import annotations

import pytest

from packages.agents.nodes.phase2_decompose import decompose_heuristic
from packages.agents.nodes.phase3_search_plan import build_search_plan
from packages.agents.nodes.phase4_evidence import build_evidence_ledger_heuristic
from packages.agents.nodes.phase5_risk import build_risk_evaluation
from packages.agents.nodes.phase6_work_package import build_work_package_plan
from packages.agents.nodes.phase7_proposal import (
    PROPOSAL_SECTIONS,
    allow_proceed_to_phase08,
    build_committee_review,
    build_proposal_draft,
)
from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


def _make_intake(case_id: str = "P7_TEST_A") -> ProjectIntake:
    return ProjectIntake.model_validate(
        {
            "case_id": case_id,
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
            "intake_rating": "A",
        }
    )


def _setup():
    intake = _make_intake()
    spec = decompose_heuristic(intake)
    spec.project_id = "1"
    plan = build_search_plan(spec)
    ledger = build_evidence_ledger_heuristic(spec, plan)
    risk_ev = build_risk_evaluation(intake, spec, plan, ledger, prefer="heuristic")
    wp = build_work_package_plan(intake, spec, risk_ev, ledger)
    return intake, spec, plan, ledger, risk_ev, wp


def test_proposal_sections_constant_count() -> None:
    assert len(PROPOSAL_SECTIONS) == 10


def test_proposal_draft_has_ten_sections() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    assert len(draft.proposal_sections) == 10
    keys = [s.key for s in draft.proposal_sections]
    assert keys == list(PROPOSAL_SECTIONS)


def test_each_section_has_content_and_sources() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    for s in draft.proposal_sections:
        assert s.content.strip()
        assert s.sources  # 至少 1 个来源


def test_innovation_points_match_wps() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    assert len(draft.innovation_points) == len(wp.work_packages)


def test_research_status_classified_by_method() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    assert len(draft.research_status) >= 1
    for row in draft.research_status:
        assert row.category
        assert row.representative_work
        assert row.gap
        assert row.relation


def test_timeline_present() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    assert len(draft.timeline) >= 3
    for entry in draft.timeline:
        assert "phase" in entry
        assert "deliverable" in entry


def test_risk_plan_includes_pivot() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    assert len(draft.risk_plan) >= 2


def test_committee_review_seven_dimensions() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    cr = build_committee_review(ledger, risk_ev, wp)
    assert len(cr.reviews) == 7
    expected_dims = {
        "题目边界", "研究现状", "创新点", "数据与 baseline",
        "实验方案", "工作量", "风险预案",
    }
    assert {r.dimension for r in cr.reviews} == expected_dims


def test_committee_questions_six() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    cr = build_committee_review(ledger, risk_ev, wp)
    assert len(cr.questions) == 6
    for q in cr.questions:
        assert q.question
        assert q.suggested_answer
        assert q.evidence_source


def test_committee_default_verdict_pass_or_conditional() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    cr = build_committee_review(ledger, risk_ev, wp)
    assert cr.overall_verdict in ("通过", "有条件通过", "需修改", "不通过")
    # 默认 heuristic ledger + A 评级 → 至少不通过的概率低
    assert cr.overall_verdict != "不通过"


def test_committee_maturity_in_a_b_c() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    cr = build_committee_review(ledger, risk_ev, wp)
    assert cr.proposal_maturity in ("A", "B", "C", "D")


def test_allow_proceed_phase08_default_true_for_A() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    cr = build_committee_review(ledger, risk_ev, wp)
    allow, reason = allow_proceed_to_phase08(cr)
    assert allow is True, reason


def test_revision_checklist_format() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    cr = build_committee_review(ledger, risk_ev, wp)
    for item in cr.revision_checklist:
        assert "priority" in item
        assert "item" in item
        assert "reason" in item
        assert "deadline" in item


def test_d_evaluation_blocks_phase08() -> None:
    intake, spec, plan, ledger, risk_ev, wp = _setup()
    risk_ev.risk_score.overall_rating = "D"
    cr = build_committee_review(ledger, risk_ev, wp)
    allow, reason = allow_proceed_to_phase08(cr)
    assert allow is False
