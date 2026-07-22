from __future__ import annotations

from paperagent.nodes.planning import _ensure_user_material_identity_queries
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery


def _full_plan(*, query_count: int) -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="bounded supplied-paper verification",
        scope="test",
        evidence_gaps=[
            EvidenceGap(gap_id=f"g{index}", description=f"supporting gap {index}")
            for index in range(1, query_count + 1)
        ],
        search_queries=[
            SearchQuery(
                query_id=f"q{index}",
                gap_id=f"g{index}",
                query=f"supporting evidence query {index}",
                source_types=["paper"],
            )
            for index in range(1, query_count + 1)
        ],
    )


def test_supplied_identity_query_displaces_lower_priority_query_when_budget_is_full() -> None:
    plan = _full_plan(query_count=2)
    request = ResearchRequest(
        question="compare a supplied baseline",
        user_material_refs=[
            "USAD: UnSupervised Anomaly Detection on Multivariate Time Series "
            "[declared role: baseline]"
        ],
    )

    updated = _ensure_user_material_identity_queries(plan, request, query_budget=2)

    assert len(updated.search_queries) == 2
    assert updated.search_queries[0].query == (
        '"USAD: UnSupervised Anomaly Detection on Multivariate Time Series"'
    )
    assert updated.search_queries[0].source_types == ["paper", "web"]
    assert {query.query_id for query in updated.search_queries} != {"q1", "q2"}
    updated.validate_query_budget(2)


def test_multiple_supplied_titles_take_priority_before_repository_supplements() -> None:
    plan = _full_plan(query_count=2)
    request = ResearchRequest(
        question="verify two supplied methods",
        user_material_refs=[
            "USAD: UnSupervised Anomaly Detection on Multivariate Time Series "
            "[declared role: baseline]",
            "Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy "
            "[declared role: parallel_module_source]",
        ],
    )

    updated = _ensure_user_material_identity_queries(plan, request, query_budget=2)

    assert [query.query for query in updated.search_queries] == [
        '"USAD: UnSupervised Anomaly Detection on Multivariate Time Series"',
        '"Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy"',
    ]
    assert all(query.source_types == ["paper", "web"] for query in updated.search_queries)


def test_existing_exact_title_paper_query_is_not_duplicated() -> None:
    title = "Graph Attention Networks"
    plan = ResearchPlan(
        status="ready",
        problem_statement="verify supplied method",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="paper identity")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="g1",
                query=f'"{title}"',
                source_types=["paper", "web"],
            )
        ],
    )
    request = ResearchRequest(
        question="verify supplied method",
        user_material_refs=[f"{title} [declared role: parallel_module_source]"],
    )

    updated = _ensure_user_material_identity_queries(plan, request, query_budget=2)

    assert [query.query for query in updated.search_queries] == [f'"{title}"']
