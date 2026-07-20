from __future__ import annotations

from datetime import UTC, datetime

from paperagent.evidence_relevance import assess_lexical_relevance, derive_research_contract
from paperagent.schemas import EvidenceGap, EvidenceItem, ResearchPlan, ResearchRequest
from paperagent.schemas.plan import SearchQuery


def test_runtime_query_terms_are_prioritized_over_verbose_planner_prose() -> None:
    planner_noise = " ".join(f"plannerterm{index}" for index in range(100))
    gap = EvidenceGap(
        gap_id="mechanism_limitations",
        description="识别专业问答中幻觉的失败机制和局限",
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement=planner_noise,
        scope=planner_noise,
        research_questions=[planner_noise],
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q-semantic-entropy",
                gap_id=gap.gap_id,
                query="semantic entropy probes hallucination detection uncertainty",
                source_types=["paper"],
            )
        ],
        success_criteria=[planner_noise],
        risks=[],
    )
    item = EvidenceItem(
        evidence_id="ev-semantic-entropy",
        source_type="paper",
        title="Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs",
        locator="https://arxiv.org/abs/2406.15927",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[gap.gap_id],
        summary=(
            "Semantic entropy probes provide robust hallucination detection and uncertainty "
            "quantification for large language models."
        ),
        content_hash="sha256:semantic-entropy",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": gap.gap_id},
    )

    contract = derive_research_contract(
        ResearchRequest(question="减少大语言模型在专业问答中的幻觉"),
        plan,
    )
    lexical = assess_lexical_relevance(item, contract)

    assert contract.positive_terms[:6] == [
        "semantic",
        "entropy",
        "probes",
        "hallucination",
        "detection",
        "uncertainty",
    ]
    assert lexical.decision == "pass"
    assert {"semantic", "entropy", "hallucination"} <= set(lexical.matched_terms)
