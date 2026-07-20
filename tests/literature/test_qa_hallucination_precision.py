from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.evidence_gap_binding import build_evidence_ledger
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
from paperagent.literature.task_query_overrides import override_task_query
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
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
            "large language model hallucination survey causes taxonomy",
            "A survey of hallucination in large language models presents a taxonomy of factual "
            "errors, causes, challenges, and mitigation methods.",
            True,
        ),
    ],
)
def test_professional_qa_candidate_guards(
    query: str, candidate: str, expected: bool
) -> None:
    assert matches_specialized_candidate_terms(query, candidate) is expected


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_comparison_evidence",
            "baseline comparison for professional QA",
            "retrieval augmented question answering hallucination baseline",
        ),
        (
            "failure_mechanism_limitation_evidence",
            "hallucination failure mechanism and limitations",
            "large language model hallucination survey causes taxonomy",
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


def test_hallucination_survey_supports_mechanism_gap_only() -> None:
    gap = EvidenceGap(
        gap_id="failure_mechanism_limitation_evidence",
        description="hallucination failure mechanism, causes, taxonomy, and limitations",
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="professional question answering hallucination reduction",
        scope="domain-specific question answering with factuality constraints",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q-survey",
                gap_id=gap.gap_id,
                query="large language model hallucination survey causes taxonomy",
                source_types=["paper"],
            )
        ],
        success_criteria=["identify direct failure-mechanism evidence"],
        risks=["domain corpus and acceptable abstention rate are unresolved"],
    )
    item = EvidenceItem(
        evidence_id="ev-hallucination-survey",
        source_type="paper",
        title=(
            "A Survey on Hallucination in Large Language Models: Principles, Taxonomy, "
            "Challenges, and Open Questions"
        ),
        locator="arxiv:2311.05232",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[gap.gap_id],
        summary=(
            "This survey studies hallucination in large language models, presents a taxonomy of "
            "factual errors and causes, analyzes challenges and limitations, and reviews detection "
            "and mitigation methods."
        ),
        content_hash="sha256:hallucination-survey",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": gap.gap_id},
    )
    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="专业问答系统中的大模型幻觉问题"),
        plan=plan,
        evidence=EvidenceBundle(
            items=[item],
            accepted_ids=[item.evidence_id],
            identity_verified_ids=[item.evidence_id],
            coverage_by_gap={gap.gap_id: 1},
        ),
    )
    support = next(value for value in supports if value.gap_id == gap.gap_id)
    assert ledger.accepted_ids == [item.evidence_id]
    assert support.decision == "accept"
    assert support.checklist_results["role_evidence_present"] is True
