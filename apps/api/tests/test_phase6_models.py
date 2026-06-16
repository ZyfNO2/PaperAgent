"""Phase 06 Pydantic + work package plan tests."""

from __future__ import annotations

import pytest

from packages.agents.nodes.phase2_decompose import decompose_heuristic
from packages.agents.nodes.phase3_search_plan import build_search_plan
from packages.agents.nodes.phase4_evidence import build_evidence_ledger_heuristic
from packages.agents.nodes.phase5_risk import build_risk_evaluation
from packages.agents.nodes.phase6_work_package import (
    allow_proceed_to_phase07,
    build_work_package_plan,
)
from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
    WorkPackageDraft,
)


def _make_intake(case_id: str = "P6_TEST_A") -> ProjectIntake:
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
    return intake, spec, plan, ledger, risk_ev


def test_work_package_plan_has_two_wps() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    assert len(p.work_packages) == 2
    assert p.work_packages[0].wp_id == "WP1"
    assert p.work_packages[1].wp_id == "WP2"


def test_work_package_chapter_assignment() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    assert p.work_packages[0].chapter == "第三章"
    assert p.work_packages[1].chapter == "第四章"


def test_each_wp_has_main_and_supporting_experiments() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    for wp in p.work_packages:
        assert wp.main_experiment.type == "主实验"
        assert len(wp.supporting_experiments) >= 1


def test_experiment_matrixes_match_wps() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    assert len(p.experiment_matrices) == len(p.work_packages)
    for mat, wp in zip(p.experiment_matrices, p.work_packages):
        assert mat.wp_id == wp.wp_id
        assert mat.main_experiment.experiment_id == wp.main_experiment.experiment_id


def test_thesis_outline_has_five_chapters() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    chapters = [c.chapter for c in p.thesis_outline]
    assert chapters == ["第一章", "第二章", "第三章", "第四章", "第五章"]
    for ch in p.thesis_outline:
        assert ch.title
        assert ch.content_summary
        assert ch.figures_needed  # 至少 1 个图表需求


def test_final_topic_default_keeps_normalized() -> None:
    """heuristic 评级 A → final_topic 用 normalized_topic，不走 pivot。"""

    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    assert p.final_topic == spec.normalized_topic
    assert p.final_topic_from_pivot is False


def test_pivot_adopted_when_decision_is_收缩() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    # 强行构造 C 评级
    risk_ev.risk_score.overall_rating = "C"
    risk_ev.decision = "收缩"
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    # 应当选 pivot_candidates[0]
    assert p.final_topic_from_pivot is True
    assert p.final_topic == risk_ev.pivot_candidates[0].new_topic


def test_allow_proceed_phase07_default_A() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    allow, reason = allow_proceed_to_phase07(p)
    assert allow is True, reason


def test_allow_proceed_phase07_blocked_on_D() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    p.allow_proceed_to_phase07 = False
    allow, reason = allow_proceed_to_phase07(p)
    assert allow is False


def test_max_writing_risk_present() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    assert p.max_writing_risk.strip() != ""


def test_innovation_binding_present() -> None:
    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    for wp in p.work_packages:
        assert wp.innovation_binding
        assert "绑定" in wp.innovation_binding or "→" in wp.innovation_binding


def test_innovation_binding_listed_for_every_wp() -> None:
    """§6 验收: 每个创新点绑定至少 1 个实验。"""

    intake, spec, plan, ledger, risk_ev = _setup()
    p = build_work_package_plan(intake, spec, risk_ev, ledger)
    for wp in p.work_packages:
        # 必有主实验 + ≥1 补充实验
        assert wp.main_experiment
        assert len(wp.supporting_experiments) >= 1
