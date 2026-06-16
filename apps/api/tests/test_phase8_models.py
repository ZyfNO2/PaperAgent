"""Phase 08 Pydantic + final package tests."""

from __future__ import annotations

import pytest

from packages.agents.nodes.phase2_decompose import decompose_heuristic
from packages.agents.nodes.phase3_search_plan import build_search_plan
from packages.agents.nodes.phase4_evidence import build_evidence_ledger_heuristic
from packages.agents.nodes.phase5_risk import build_risk_evaluation
from packages.agents.nodes.phase6_work_package import build_work_package_plan
from packages.agents.nodes.phase7_proposal import (
    build_committee_review,
    build_proposal_draft,
)
from packages.agents.nodes.phase8_final_package import (
    allow_archive_to_thesis,
    build_final_package,
)
from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


def _make_intake(case_id: str = "P8_TEST_A") -> ProjectIntake:
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
    draft = build_proposal_draft(intake, spec.normalized_topic, ledger, wp, risk_ev)
    review = build_committee_review(ledger, risk_ev, wp)
    return intake, spec, plan, ledger, risk_ev, wp, draft, review


def test_final_package_assembles_10_sections() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert len(pkg.proposal_sections) == 10


def test_final_topic_present() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert pkg.final_topic.topic_zh
    assert pkg.final_topic.boundary
    assert pkg.final_topic.topic_en  # MVP 自动加英文名


def test_evidence_archive_seven_types() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    types = {e.evidence_type for e in pkg.evidence_archive}
    assert types == {
        "论文", "综述", "数据集候选", "Baseline 候选",
        "评价指标", "实验模板", "学位论文模板",
    }


def test_qa_pairs_seven() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert len(pkg.qa_pairs) == 7
    for qa in pkg.qa_pairs:
        assert qa.question
        assert qa.answer
        assert qa.evidence


def test_future_stages_nine() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert len(pkg.future_stages) == 9
    for s in pkg.future_stages:
        assert s.stage
        assert s.task
        assert s.deliverable


def test_proposal_markdown_nonempty() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert len(pkg.proposal_markdown) > 500
    # 必含所有 10 节标题
    for s in draft.proposal_sections:
        assert s.title in pkg.proposal_markdown


def test_backend_verification_pass() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert pkg.backend_verification == "PASS"


def test_ui_and_playwright_blocked() -> None:
    """apps/web 还没建, UI / Playwright 必为 BLOCKED。"""

    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert pkg.ui_verification == "BLOCKED"
    assert pkg.playwright_verification == "BLOCKED"


def test_thesis_outline_5_chapters() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    chapters = [o["chapter"] for o in pkg.thesis_outline]
    assert chapters == ["第一章", "第二章", "第三章", "第四章", "第五章"]


def test_default_ready_for_thesis() -> None:
    """heuristic 完整链路 + A 评级 → ready_for_thesis=True。"""

    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert pkg.ready_for_thesis is True
    assert pkg.block_reasons == []


def test_allow_archive_to_thesis_default() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    allow, reason = allow_archive_to_thesis(pkg)
    assert allow is True, reason


def test_d_evaluation_blocks_archive() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    risk_ev.risk_score.overall_rating = "D"
    review.allow_proceed_to_phase08 = False
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert pkg.ready_for_thesis is False
    assert any("verdict" in r or "maturity" in r for r in pkg.block_reasons)


def test_work_package_summaries_match() -> None:
    intake, spec, plan, ledger, risk_ev, wp, draft, review = _setup()
    pkg = build_final_package(draft, wp, review, risk_ev, ledger)
    assert len(pkg.work_packages) == 2
    for s in pkg.work_packages:
        assert s.wp_id in ("WP1", "WP2")
        assert s.chapter in ("第三章", "第四章")
