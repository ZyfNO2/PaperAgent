from __future__ import annotations

from paperagent.nodes.planning import (
    _ensure_baseline_role_query,
    _ensure_methodology_asset_queries,
)
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery


def _plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="reduce inference cost while preserving task accuracy",
        scope="bounded reproducible pilot",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="general task evidence")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="g1",
                query="general task evidence",
                source_types=["paper"],
            )
        ],
    )


def test_planner_adds_baseline_module_and_dataset_lanes() -> None:
    request = ResearchRequest(question="design a task-matched incremental method")
    with_baseline = _ensure_baseline_role_query(_plan(), query_budget=10)
    updated = _ensure_methodology_asset_queries(with_baseline, request, query_budget=10)
    query_text = "\n".join(query.query.casefold() for query in updated.search_queries)
    assert "established reproducible baseline" in query_text
    assert "independent parallel method" in query_text
    assert "dataset benchmark evaluation protocol" in query_text


def test_identity_lane_remains_ahead_of_generated_methodology_lanes() -> None:
    plan = _plan().model_copy(
        update={
            "evidence_gaps": [
                EvidenceGap(
                    gap_id="user-material-baseline",
                    description="verify declared baseline identity",
                ),
                *_plan().evidence_gaps,
            ],
            "search_queries": [
                SearchQuery(
                    query_id="q-user-material-baseline",
                    gap_id="user-material-baseline",
                    query='"Declared Baseline"',
                    source_types=["paper", "web"],
                ),
                *_plan().search_queries,
            ],
        }
    )
    updated = _ensure_baseline_role_query(plan, query_budget=4)
    assert updated.search_queries[0].gap_id == "user-material-baseline"
    assert any("reproducible baseline" in item.query for item in updated.search_queries)
