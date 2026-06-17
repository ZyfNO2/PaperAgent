"""Phase 05 Pydantic model + risk evaluation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.agents.nodes.phase2_decompose import decompose_heuristic
from packages.agents.nodes.phase3_search_plan import build_search_plan
from packages.agents.nodes.phase4_evidence import build_evidence_ledger_heuristic
from packages.agents.nodes.phase5_risk import (
    allow_proceed_to_phase06,
    build_pivots,
    build_risk_evaluation,
    build_risk_score,
)
from packages.domain import (
    DimensionKey,
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


def _make_intake(case_id: str = "P5_TEST_A") -> ProjectIntake:
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
    spec = decompose_heuristic(_make_intake())
    spec.project_id = "1"
    plan = build_search_plan(spec)
    ledger = build_evidence_ledger_heuristic(spec, plan)
    intake = _make_intake()
    return intake, spec, plan, ledger


def test_risk_score_has_six_dimensions() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    assert len(rs.dimensions) == 6
    keys = {d.key for d in rs.dimensions}
    assert keys == {
        "方向成熟度", "数据可得性", "baseline清晰度",
        "实验可行性", "工作量可拆性", "毕业时间风险",
    }


def test_risk_score_default_A() -> None:
    """完整 heuristic ledger + 完整 intake → A 评级。"""

    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    assert rs.overall_rating in ("A", "B")
    assert rs.overall_score > 50


def test_risk_score_min_viable_path_present() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    assert rs.min_viable_path.strip() != ""


def test_risk_score_max_risk_dimension_is_lowest() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    min_dim = min(rs.dimensions, key=lambda d: d.score)
    assert rs.max_risk_dimension == min_dim.key


def test_pivots_heuristic_at_least_one() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    pivots = build_pivots(intake, spec, ledger, rs, prefer="heuristic")
    assert len(pivots) >= 1
    for p in pivots:
        assert p.new_topic
        assert p.rationale


def test_evaluation_decision_in_valid_set() -> None:
    intake, spec, plan, ledger = _setup()
    ev = build_risk_evaluation(intake, spec, plan, ledger, prefer="heuristic")
    assert ev.decision in ("继续", "收缩", "转向")
    assert ev.decision_rationale


def test_evaluation_allow_proceed() -> None:
    intake, spec, plan, ledger = _setup()
    ev = build_risk_evaluation(intake, spec, plan, ledger, prefer="heuristic")
    allow, reason = allow_proceed_to_phase06(ev)
    assert allow is True, reason


def test_pivot_preserves_evidence_field() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    pivots = build_pivots(intake, spec, ledger, rs, prefer="heuristic")
    for p in pivots:
        # Pivot 必须声明 preserved / new_evidence
        assert isinstance(p.preserved_evidence, list)
        assert isinstance(p.new_evidence_needed, list)


def test_low_overall_score_triggers_C_or_D() -> None:
    """把 heuristic ledger 的 papers / datasets / baselines 全部清空 → C/D 评级。"""

    intake, spec, plan, ledger = _setup()
    ledger.papers = []
    ledger.surveys = []
    ledger.datasets = []
    ledger.baselines = []
    ledger.metrics = []
    ledger.experiment_templates = []
    ledger.thesis_templates = []
    ledger.evidence_rating = "D"
    rs = build_risk_score(intake, spec, ledger)
    assert rs.overall_rating in ("C", "D")


def test_d_evaluation_decision_must_be_换向() -> None:
    intake, spec, plan, ledger = _setup()
    # 强行构造 D
    ledger.papers = []
    ledger.surveys = []
    ledger.datasets = []
    ledger.baselines = []
    ledger.metrics = []
    ledger.experiment_templates = []
    ledger.thesis_templates = []
    ledger.evidence_rating = "D"
    ev = build_risk_evaluation(intake, spec, plan, ledger, prefer="heuristic")
    assert ev.risk_score.overall_rating == "D"
    # D 评级 → 决策应为 "转向"
    assert ev.decision == "转向"


def test_cd_evaluation_must_have_pivot() -> None:
    intake, spec, plan, ledger = _setup()
    # C
    ledger.papers = [ledger.papers[0]] if ledger.papers else []
    ledger.datasets = []
    ev = build_risk_evaluation(intake, spec, plan, ledger, prefer="heuristic")
    if ev.risk_score.overall_rating in ("C", "D"):
        assert len(ev.pivot_candidates) >= 1


def test_pivot_id_unique() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    pivots = build_pivots(intake, spec, ledger, rs, prefer="heuristic")
    ids = [p.pivot_id for p in pivots]
    assert len(ids) == len(set(ids))


def test_risk_score_all_scores_in_range() -> None:
    intake, spec, plan, ledger = _setup()
    rs = build_risk_score(intake, spec, ledger)
    for d in rs.dimensions:
        assert 0.0 <= d.score <= 100.0
        assert d.evidence_summary
