"""Phase 03 Pydantic model + search plan generator tests."""

from __future__ import annotations

from packages.agents.nodes.phase2_decompose import decompose_heuristic
from packages.agents.nodes.phase3_search_plan import (
    allow_proceed_to_phase04,
    build_search_plan,
)
from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


def _make_intake(case_id: str = "P3_TEST_A") -> ProjectIntake:
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


def test_plan_has_seven_layers() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    layer_ids = [l.layer for l in plan.query_layers]
    assert layer_ids == ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]


def test_plan_total_queries_meets_threshold() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    total = sum(len(l.queries) for l in plan.query_layers)
    assert total >= 10, f"总检索词仅 {total}，要求 ≥ 10"


def test_plan_extracts_english_keywords_from_gnn_topic() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    all_queries = " ".join(q for l in plan.query_layers for q in l.queries).lower()
    assert "graph neural network" in all_queries or "gnn" in all_queries
    assert "recommendation" in all_queries or "recommender" in all_queries


def test_plan_includes_chinese_thesis_templates() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    l5 = next(l for l in plan.query_layers if l.layer == "L5")
    assert any("学位论文" in q or "开题" in q for q in l5.queries)


def test_plan_wp_queries_meet_minimum() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    for wp_q in plan.work_package_queries:
        assert len(wp_q.query_groups) >= 2


def test_plan_allow_proceed_phase04() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    allow, reason = allow_proceed_to_phase04(plan)
    assert allow is True, reason


def test_plan_risk_flags_for_topic_with_many_risks() -> None:
    intake = _make_intake("P3_RISKY")
    intake = intake.model_copy(
        update={"raw_topic": "基于大模型的通用智能实时高精度全自动化开题助手"}
    )
    spec = decompose_heuristic(intake)
    plan = build_search_plan(spec)
    # ≥4 个风险词 → B
    assert plan.maturity_rating == "B"
    assert any("高风险词" in f for f in plan.risk_flags)


def test_plan_uses_carried_constraints() -> None:
    spec = decompose_heuristic(_make_intake())
    plan = build_search_plan(spec)
    assert "图神经网络" in plan.carried_constraints
