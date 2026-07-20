from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.evidence_gap_binding import build_evidence_ledger
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
from paperagent.literature.task_query_overrides import override_task_query
from paperagent.retrieval.verify_evidence import _plan_with_prepared_queries
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    PreparedQuery,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.plan import SearchQuery


@pytest.mark.parametrize(
    ("query", "candidate", "expected"),
    [
        (
            "retrieval augmented question answering hallucination baseline",
            "A grounded Islamic QA system uses retrieval and citation verification to reduce "
            "hallucination in domain-specific question answering.",
            True,
        ),
        (
            "retrieval augmented question answering hallucination baseline",
            "EVOR evolves retrieval databases for code generation and repository-level programs.",
            False,
        ),
        (
            "semantic entropy probes hallucination detection uncertainty",
            "Semantic entropy probes provide reliable hallucination detection through uncertainty "
            "quantification in large language models.",
            True,
        ),
    ],
)
def test_professional_qa_candidate_guards(query: str, candidate: str, expected: bool) -> None:
    assert matches_specialized_candidate_terms(query, candidate) is expected


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_comparison_evidence",
            "baseline comparison for professional QA hallucination reduction",
            "retrieval augmented question answering hallucination baseline",
        ),
        (
            "failure_mechanism_limitation_evidence",
            "hallucination reduction failure mechanism and limitations",
            "semantic entropy probes hallucination detection uncertainty",
        ),
        (
            "parallel_method_evidence",
            "parallel hallucination reduction with retrieval verification and uncertainty",
            "question answering hallucination reduction retrieval verification uncertainty",
        ),
    ],
)
def test_professional_qa_queries_are_role_specific(
    gap_id: str, description: str, expected: str
) -> None:
    result = override_task_query(
        "generic professional QA hallucination query",
        gap_id=gap_id,
        gap_description=description,
        research_context="专业问答系统中的大模型幻觉问题",
    )
    assert result.changed is True
    assert result.query == expected


def test_semantic_entropy_probes_supports_mechanism_gap() -> None:
    gap = EvidenceGap(
        gap_id="failure_mechanism_limitation_evidence",
        description="hallucination failure mechanism, uncertainty, and detection limitations",
    )
    original_query = "professional question answering hallucination mechanism evidence"
    refined_query = "semantic entropy probes hallucination detection uncertainty"
    plan = ResearchPlan(
        status="ready",
        problem_statement="professional question answering hallucination reduction",
        scope="domain-specific question answering with factuality constraints",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q-semantic-entropy",
                gap_id=gap.gap_id,
                query=original_query,
                source_types=["paper"],
            )
        ],
        success_criteria=["identify direct failure-mechanism evidence"],
        risks=["domain corpus and acceptable abstention rate are unresolved"],
    )
    effective_plan = _plan_with_prepared_queries(
        plan,
        [
            PreparedQuery(
                query_id="q-semantic-entropy",
                gap_id=gap.gap_id,
                query=refined_query,
                original_query=original_query,
                refinement_reason="canonicalized professional-QA hallucination mechanism query",
                source_types=["paper"],
                round=1,
            )
        ],
    )
    assert effective_plan is not None
    assert effective_plan.search_queries[0].query == refined_query

    item = EvidenceItem(
        evidence_id="ev-semantic-entropy-probes",
        source_type="paper",
        title="Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs",
        locator="arxiv:2406.15927",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[gap.gap_id],
        summary=(
            "Hallucinations are a major challenge to the practical adoption of large language "
            "models. We propose semantic entropy probes, a reliable uncertainty quantification "
            "method that detects hallucinations while reducing sampling overhead."
        ),
        content_hash="sha256:semantic-entropy-probes",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": gap.gap_id},
    )
    _, lexical, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="专业问答系统中的大模型幻觉问题"),
        plan=effective_plan,
        evidence=EvidenceBundle(
            items=[item],
            accepted_ids=[item.evidence_id],
            identity_verified_ids=[item.evidence_id],
            coverage_by_gap={gap.gap_id: 1},
        ),
    )
    support = next(value for value in supports if value.gap_id == gap.gap_id)
    assert lexical[0].decision == "pass"
    assert ledger.accepted_ids == [item.evidence_id]
    assert support.decision == "accept"
    assert support.support_type == "direct_support"
    assert support.supported_claim is not None
