"""Phase 04 Pydantic model + evidence ledger tests."""

from __future__ import annotations

from packages.agents.nodes.phase2_decompose import decompose_heuristic
from packages.agents.nodes.phase3_search_plan import build_search_plan
from packages.agents.nodes.phase4_evidence import (
    build_evidence_ledger,
    build_evidence_ledger_heuristic,
)
from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


def _make_intake(case_id: str = "P4_TEST_A") -> ProjectIntake:
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


def _setup() -> tuple:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    spec.project_id = "1"
    return spec, plan


def test_heuristic_ledger_has_minimum_papers() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    assert len(ledger.papers) >= 5
    assert len(ledger.surveys) >= 1
    assert len(ledger.datasets) >= 2
    assert len(ledger.baselines) >= 2
    assert len(ledger.metrics) >= 1
    assert len(ledger.experiment_templates) >= 1
    assert len(ledger.thesis_templates) >= 1


def test_heuristic_ledger_rates_A_by_default() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    assert ledger.evidence_rating == "A"
    assert ledger.risk_flags == []


def test_papers_have_evidence_score_in_range() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    for p in ledger.papers:
        assert 0.0 <= p.evidence_score <= 1.0


def test_baselines_have_workspace_indicators() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    for b in ledger.baselines:
        assert b.name
        assert b.reproduce_difficulty in ("低", "中", "高", "未知")


def test_datasets_wp_binding_round_trip() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    wp_bindings = {w for d in ledger.datasets for w in d.wp_binding}
    assert wp_bindings <= {"WP1", "WP2"}


def test_thesis_templates_have_toc_outline() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    for t in ledger.thesis_templates:
        assert len(t.toc_outline) >= 3


def test_metric_set_reproducible() -> None:
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    for m in ledger.metrics:
        assert m.reproducible is True


def test_empty_eval_metrics_triggers_low_rating() -> None:
    spec, plan = _setup()
    spec.evaluation_metrics = []
    ledger = build_evidence_ledger_heuristic(spec, plan)
    # 缺 metrics → D
    assert ledger.evidence_rating == "D"
    assert any("评价指标" in f for f in ledger.risk_flags)


def test_paper_count_below_5_triggers_C() -> None:
    spec, plan = _setup()
    spec, plan = _setup()
    ledger = build_evidence_ledger_heuristic(spec, plan)
    ledger.papers = ledger.papers[:3]  # 强制少于 5
    # 重新评级
    from packages.agents.nodes.phase4_evidence import _rate
    rating, flags = _rate(
        papers=ledger.papers, surveys=ledger.surveys,
        datasets=ledger.datasets, baselines=ledger.baselines,
        metrics=ledger.metrics, exp=ledger.experiment_templates,
        thesis=ledger.thesis_templates,
    )
    assert rating == "C"
    assert any("论文证据不足" in f for f in flags)
