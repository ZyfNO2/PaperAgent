from __future__ import annotations

from paperagent.nodes.planning import _normalize_nonblocking_clarification
from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery


def _need_human_plan(*, include_queries: bool = True) -> ResearchPlan:
    gap = EvidenceGap(
        gap_id="baseline_comparison",
        description="reproducible baseline and strong comparison evidence",
    )
    return ResearchPlan(
        status="need_human",
        problem_statement="Evaluate a multi-behavior recommendation system.",
        scope="Public evidence retrieval before private deployment choices.",
        evidence_gaps=[gap],
        search_queries=(
            [
                SearchQuery(
                    query_id="q-baseline",
                    gap_id=gap.gap_id,
                    query="multi-behavior recommendation baseline comparison",
                    source_types=["paper"],
                )
            ]
            if include_queries
            else []
        ),
        success_criteria=["Identify one reproducible baseline."],
        risks=["private behavior definitions remain unknown"],
        clarification_question="Which behavior types and deployment limits should constrain the pilot?",
    )


def test_complete_query_contract_promotes_clarification_to_nonblocking_ready() -> None:
    original = _need_human_plan()

    normalized = _normalize_nonblocking_clarification(original)

    assert normalized.status == "ready"
    assert normalized.clarification_question == original.clarification_question
    assert normalized.evidence_gaps == original.evidence_gaps
    assert normalized.search_queries == original.search_queries


def test_missing_query_contract_remains_need_human() -> None:
    original = _need_human_plan(include_queries=False)

    normalized = _normalize_nonblocking_clarification(original)

    assert normalized.status == "need_human"
    assert normalized is original
