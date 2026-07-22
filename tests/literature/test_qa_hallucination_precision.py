from __future__ import annotations

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.retrieval.verify_evidence import _plan_with_runtime_queries
from paperagent.schemas import EvidenceGap, ResearchPlan, SearchCandidate
from paperagent.schemas.plan import SearchQuery


def test_runtime_query_provenance_survives_consumed_prepared_batch() -> None:
    gap = EvidenceGap(
        gap_id="mechanism-evidence",
        description="glacier calving boundary-condition failure mechanism",
    )
    original_query = "glacier simulation mechanism evidence"
    refined_query = "glacier calving finite-volume boundary uncertainty"
    plan = ResearchPlan(
        status="ready",
        problem_statement="accelerate glacier calving simulation",
        scope="physics-informed surrogate with explicit uncertainty",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q-runtime-provenance",
                gap_id=gap.gap_id,
                query=original_query,
                source_types=["paper"],
            )
        ],
        success_criteria=["identify direct mechanism evidence"],
        risks=["boundary observations are sparse"],
    )
    candidate = SearchCandidate(
        candidate_id="paper-glacier-calving",
        query_id="q-runtime-provenance",
        gap_id=gap.gap_id,
        source_type="paper",
        title="Finite-Volume Glacier Calving under Boundary Uncertainty",
        locator="https://example.org/paper/glacier-calving",
        snippet=(
            "A finite-volume study characterizes glacier calving sensitivity to uncertain "
            "boundary conditions."
        ),
        provider="literature_retrieval",
        metadata={
            "query_text": refined_query,
            "verification_status": "verified",
        },
    )

    effective_plan = _plan_with_runtime_queries(plan, [], [candidate])

    assert effective_plan is not None
    assert effective_plan.search_queries[0].query == refined_query
    assert matches_required_candidate_terms(refined_query, f"{candidate.title} {candidate.snippet}")


def test_runtime_query_does_not_make_cross_domain_candidate_relevant() -> None:
    query = "glacier calving finite-volume boundary uncertainty"
    candidate = "Finite-volume combustion modelling with uncertain chemical boundaries."
    assert not matches_required_candidate_terms(query, candidate)
