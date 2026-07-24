from __future__ import annotations

from paperagent.nodes.planning import (
    _ensure_user_material_identity_queries,
    _normalize_nonblocking_clarification,
)
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery


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
        clarification_question=(
            "Which behavior types and deployment limits should constrain the pilot?"
        ),
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


def test_public_supplied_title_adds_prioritized_identity_query() -> None:
    original = _need_human_plan()
    request = ResearchRequest(
        question="Assess how to use my supplied baseline.",
        user_material_refs=[
            "LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation "
            "[declared role: baseline_candidate]"
        ],
    )

    normalized = _ensure_user_material_identity_queries(
        original,
        request,
        query_budget=10,
    )

    assert normalized.status == "ready"
    assert len(normalized.evidence_gaps) == 2
    assert len(normalized.search_queries) == 3
    assert normalized.evidence_gaps[0].gap_id == "user-material-01-identity"
    assert normalized.evidence_gaps[0].minimum_accepted_items == 1
    assert normalized.search_queries[0].query == (
        '"LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation"'
    )
    assert normalized.search_queries[0].source_types == ["paper", "web"]
    assert normalized.search_queries[1].query == (
        '"LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation" '
        "official implementation code repository"
    )
    assert normalized.search_queries[1].source_types == ["repository", "web"]
    assert normalized.search_queries[0].gap_id == normalized.evidence_gaps[0].gap_id
    assert normalized.search_queries[1].gap_id == normalized.evidence_gaps[0].gap_id


def test_opaque_upload_placeholder_does_not_create_identity_query() -> None:
    original = _need_human_plan()
    request = ResearchRequest(
        question="Assess my supplied method.",
        user_material_refs=[
            "user-supplied contrastive recommendation paper [declared role: module_candidate]"
        ],
    )

    normalized = _ensure_user_material_identity_queries(
        original,
        request,
        query_budget=10,
    )

    assert normalized is original


def test_supplied_title_does_not_exceed_query_budget() -> None:
    original = _need_human_plan()
    request = ResearchRequest(
        question="Assess my supplied baseline.",
        user_material_refs=[
            "LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation "
            "[declared role: baseline_candidate]"
        ],
    )

    normalized = _ensure_user_material_identity_queries(
        original,
        request,
        query_budget=1,
    )

    assert normalized.status == "ready"
    assert len(normalized.evidence_gaps) == 1
    assert normalized.evidence_gaps[0].gap_id == "user-material-01-identity"
    assert len(normalized.search_queries) == 1
    assert normalized.search_queries[0].gap_id == normalized.evidence_gaps[0].gap_id
