from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError


def test_run_budgets__negative_value__is_rejected() -> None:
    from paperagent.schemas import RunBudgets

    with pytest.raises(ValidationError):
        RunBudgets(max_llm_calls=-1)


def test_run_context__unknown_field__is_rejected_and_frozen() -> None:
    from paperagent.schemas import RunBudgets, RunContext

    with pytest.raises(ValidationError):
        RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(),
            extra_field=True,
        )


def test_research_request__normalization__trims_and_deduplicates() -> None:
    from paperagent.schemas import ResearchRequest

    request = ResearchRequest(
        question="  evaluate citations  ",
        required_constraints=["offline", " offline ", "small"],
    )
    assert request.question == "evaluate citations"
    assert request.required_constraints == ["offline", "small"]


def test_research_request__short_question__is_rejected() -> None:
    from paperagent.schemas import ResearchRequest

    with pytest.raises(ValidationError):
        ResearchRequest(question="x")


def test_research_plan__ready_without_gap__is_rejected() -> None:
    from paperagent.schemas import ResearchPlan

    with pytest.raises(ValidationError):
        ResearchPlan(
            status="ready",
            problem_statement="p",
            scope="s",
            research_questions=["q"],
            evidence_gaps=[],
            search_queries=[],
            success_criteria=["c"],
            risks=[],
        )


def test_research_plan__query_unknown_gap__is_rejected() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    with pytest.raises(ValidationError):
        ResearchPlan(
            status="ready",
            problem_statement="p",
            scope="s",
            research_questions=["q"],
            evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
            search_queries=[SearchQuery(query_id="q1", gap_id="g2", query="search")],
            success_criteria=["c"],
            risks=[],
        )


def test_evidence_bundle__status_sets_must_match_items() -> None:
    from paperagent.schemas import EvidenceBundle, EvidenceItem

    item = EvidenceItem(
        evidence_id="ev-1",
        source_type="web",
        title="Fixture",
        locator="fixture://ev-1",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["g1"],
        summary="summary",
        content_hash="sha256:1",
    )
    with pytest.raises(ValidationError):
        EvidenceBundle(items=[item], rejected_ids=["ev-1"])


def test_quality_decision__repair_target_must_match_verdict() -> None:
    from paperagent.schemas import QualityDecision

    with pytest.raises(ValidationError):
        QualityDecision(
            verdict="repair_method",
            reason_codes=["Q_MISSING_HYPOTHESIS"],
            repair_target="retrieval",
        )


def test_final_report__completed_without_limitations__is_rejected() -> None:
    from paperagent.schemas import FinalReport

    with pytest.raises(ValidationError):
        FinalReport(
            status="completed",
            executive_summary="done",
            verified_findings=[],
            inferred_findings=[],
            limitations=[],
            next_actions=[],
            evidence_ids=[],
        )


def test_research_plan__ready_with_clarification_is_allowed() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="p",
        scope="s",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
        search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="search")],
        success_criteria=["c"],
        risks=[],
        clarification_question="?",
    )

    assert plan.clarification_question == "?"
    assert plan.block_reason is None


def test_research_plan__ready_with_block_reason_is_rejected() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    with pytest.raises(ValidationError, match="cannot include"):
        ResearchPlan(
            status="ready",
            problem_statement="p",
            scope="s",
            evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
            search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="search")],
            success_criteria=["c"],
            risks=[],
            block_reason="blocked",
        )


def test_research_plan__need_human_without_clarification_is_rejected() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    with pytest.raises(ValidationError, match="requires clarification"):
        ResearchPlan(
            status="need_human",
            problem_statement="p",
            scope="s",
            evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
            search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="search")],
            success_criteria=["c"],
            risks=[],
        )


def test_research_plan__need_human_with_block_reason_is_rejected() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    with pytest.raises(ValidationError, match="cannot include block_reason"):
        ResearchPlan(
            status="need_human",
            problem_statement="p",
            scope="s",
            evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
            search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="search")],
            success_criteria=["c"],
            risks=[],
            clarification_question="?",
            block_reason="blocked",
        )


def test_research_plan__blocked_without_reason_is_rejected() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    with pytest.raises(ValidationError, match="requires block_reason"):
        ResearchPlan(
            status="blocked",
            problem_statement="p",
            scope="s",
            evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
            search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="search")],
            success_criteria=["c"],
            risks=[],
        )


def test_research_plan__blocked_with_clarification_is_rejected() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    with pytest.raises(ValidationError, match="cannot include clarification"):
        ResearchPlan(
            status="blocked",
            problem_statement="p",
            scope="s",
            evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
            search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="search")],
            success_criteria=["c"],
            risks=[],
            block_reason="blocked",
            clarification_question="?",
        )


def test_research_plan__query_count_exceeds_budget() -> None:
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="p",
        scope="s",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="d")],
        search_queries=[
            SearchQuery(query_id="q1", gap_id="g1", query="s1"),
            SearchQuery(query_id="q2", gap_id="g1", query="s2"),
        ],
        success_criteria=["c"],
        risks=[],
    )
    with pytest.raises(ValueError, match="exceeds budget"):
        plan.validate_query_budget(1)
