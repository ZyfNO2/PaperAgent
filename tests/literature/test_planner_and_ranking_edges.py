from __future__ import annotations

import pytest

from literature_fixtures import provider_result
from paperagent.literature.merge import merge_provider_results
from paperagent.literature.planner import plan_literature_queries
from paperagent.literature.ranking import rank_papers
from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery
from paperagent.schemas.literature import (
    LiteratureFilters,
    LiteratureQueryPlan,
    ProviderPaper,
    QueryLane,
)


def ready_plan(
    gaps: list[EvidenceGap], queries: list[SearchQuery], *, status: str = "ready"
) -> ResearchPlan:
    kwargs: dict[str, object] = {}
    if status == "blocked":
        kwargs["block_reason"] = "blocked"
    return ResearchPlan(
        status=status,
        problem_statement="p",
        scope="scope",
        research_questions=["q"],
        evidence_gaps=gaps,
        search_queries=queries,
        success_criteria=["c"],
        risks=[],
        **kwargs,
    )


def test_planner_rejects_non_ready_plan() -> None:
    plan = ready_plan([], [], status="blocked")
    with pytest.raises(ValueError, match="requires a ready"):
        plan_literature_queries(plan, question="question")


def test_planner_synthesizes_missing_required_gap_lane() -> None:
    plan = ready_plan(
        [
            EvidenceGap(gap_id="method", description="method"),
            EvidenceGap(gap_id="recent", description="latest preprint progress"),
        ],
        [SearchQuery(query_id="q1", gap_id="method", query="method approach")],
    )
    literature = plan_literature_queries(plan, question="What is new?")
    assert [lane.lane_id for lane in literature.query_lanes] == ["q1", "gap-recent"]
    assert literature.query_lanes[1].purpose == "recent_progress"
    assert literature.query_lanes[1].source_preferences == ["openalex", "arxiv"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("baseline comparison", "baseline"),
        ("evaluation metric", "evaluation_metric"),
        ("contradictory conflict evidence", "contradictory_evidence"),
        ("dataset corpus", "benchmark_dataset"),
    ],
)
def test_planner_maps_query_purpose(text: str, expected: str) -> None:
    plan = ready_plan(
        [EvidenceGap(gap_id="g", description=text)],
        [SearchQuery(query_id="q", gap_id="g", query=text)],
    )
    literature = plan_literature_queries(plan, question="question")
    assert literature.query_lanes[0].purpose == expected


def test_planner_caps_lanes_at_four() -> None:
    gaps = [EvidenceGap(gap_id=f"g{i}", description="method") for i in range(5)]
    queries = [SearchQuery(query_id=f"q{i}", gap_id=f"g{i}", query=f"method {i}") for i in range(5)]
    with pytest.raises(ValueError, match="required gaps have no query lane"):
        plan_literature_queries(ready_plan(gaps, queries), question="question")


def _literature_plan(filters: LiteratureFilters | None = None) -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question="retrieval method",
        scope="IR",
        required_gap_ids=["g"],
        query_lanes=[
            QueryLane(
                lane_id="l",
                purpose="method",
                query="retrieval method",
                gap_ids=["g"],
            )
        ],
        filters=filters or LiteratureFilters(),
    )


def test_ranking_handles_missing_metadata_and_out_of_range_year() -> None:
    unknown = ProviderPaper(provider_record_id="u", title="Unknown")
    old = ProviderPaper(
        provider_record_id="o",
        title="Retrieval Method",
        year=1999,
        matched_gap_ids=["g"],
    )
    papers = merge_provider_results([provider_result("openalex", "success", [unknown, old])])
    ranked = rank_papers(
        papers,
        _literature_plan(LiteratureFilters(year_min=2020, year_max=2026)),
        now_year=2026,
    )
    by_title = {paper.canonical_title: paper for paper in ranked}
    assert by_title["Unknown"].rank_features is not None
    assert by_title["Unknown"].rank_features.recency_fit == 0.25
    assert by_title["Retrieval Method"].rank_features.recency_fit == 0.0


def test_ranking_empty_query_overlap_is_zero() -> None:
    raw = ProviderPaper(provider_record_id="p", title="Completely Different")
    paper = merge_provider_results([provider_result("openalex", "success", [raw])])
    ranked = rank_papers(paper, _literature_plan(), now_year=2026)
    assert ranked[0].rank_features is not None
    assert ranked[0].rank_features.relevance == 0.0
