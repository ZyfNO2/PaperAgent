from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/paperagent/evidence_relevance.py"
TEST = ROOT / "tests/review/test_research_contract_priority.py"

OLD = '''def derive_research_contract(
    request: ResearchRequest | None,
    plan: ResearchPlan | None,
) -> ResearchContract:
    required_gaps = [gap.gap_id for gap in plan.evidence_gaps if gap.required] if plan else []
    positive_sources: list[str] = []
    if request is not None:
        positive_sources.extend(_terms(request.question))
        positive_sources.extend(_terms(request.domain_hint))
        for constraint in request.required_constraints:
            positive_sources.extend(_terms(constraint))
    if plan is not None:
        positive_sources.extend(_terms(plan.problem_statement))
        positive_sources.extend(_terms(plan.scope))
        for question in plan.research_questions:
            positive_sources.extend(_terms(question))
        for gap in plan.evidence_gaps:
            positive_sources.extend(_terms(gap.description))
        for query in plan.search_queries:
            positive_sources.extend(_terms(query.query))
        for criterion in plan.success_criteria:
            positive_sources.extend(_terms(criterion))
    problem_terms = _terms(plan.problem_statement) if plan is not None else []
    return ResearchContract(
        task_type=problem_terms[0] if problem_terms else None,
        domain=request.domain_hint if request else None,
        deployment_constraints=list(request.required_constraints) if request else [],
        research_claim=(
            plan.problem_statement if plan else (request.question if request else None)
        ),
        positive_terms=_dedupe(positive_sources),
        required_gap_ids=required_gaps,
        assumptions=list(plan.risks) if plan else [],
    )
'''

NEW = '''def derive_research_contract(
    request: ResearchRequest | None,
    plan: ResearchPlan | None,
) -> ResearchContract:
    required_gaps = [gap.gap_id for gap in plan.evidence_gaps if gap.required] if plan else []
    positive_sources: list[str] = []

    # Runtime-approved search queries are the most precise cross-language description of
    # the evidence being requested. Keep them ahead of verbose planner prose so the
    # bounded contract vocabulary cannot discard them.
    if plan is not None:
        for query in plan.search_queries:
            positive_sources.extend(_terms(query.query))
    if request is not None:
        positive_sources.extend(_terms(request.question))
        positive_sources.extend(_terms(request.domain_hint))
        for constraint in request.required_constraints:
            positive_sources.extend(_terms(constraint))
    if plan is not None:
        positive_sources.extend(_terms(plan.problem_statement))
        positive_sources.extend(_terms(plan.scope))
        for question in plan.research_questions:
            positive_sources.extend(_terms(question))
        for gap in plan.evidence_gaps:
            positive_sources.extend(_terms(gap.description))
        for criterion in plan.success_criteria:
            positive_sources.extend(_terms(criterion))
    problem_terms = _terms(plan.problem_statement) if plan is not None else []
    return ResearchContract(
        task_type=problem_terms[0] if problem_terms else None,
        domain=request.domain_hint if request else None,
        deployment_constraints=list(request.required_constraints) if request else [],
        research_claim=(
            plan.problem_statement if plan else (request.question if request else None)
        ),
        positive_terms=_dedupe(positive_sources),
        required_gap_ids=required_gaps,
        assumptions=list(plan.risks) if plan else [],
    )
'''

TEST_CONTENT = '''from __future__ import annotations

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
'''


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    if OLD in source:
        SOURCE.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
    elif NEW not in source:
        raise RuntimeError("derive_research_contract implementation did not match expected source")
    TEST.write_text(TEST_CONTENT, encoding="utf-8")


if __name__ == "__main__":
    main()
