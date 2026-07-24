from __future__ import annotations

from typing import cast

import pytest

from paperagent import claw_benchmark_adapter as adapter
from paperagent.academic_methodology import ExperimentArmType
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery
from paperagent.state import PaperAgentState


def _plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="Evaluate an evidence-backed method.",
        scope="Use reproducible comparisons and explicit failure analysis.",
        evidence_gaps=[
            EvidenceGap(
                gap_id="g-baseline",
                description="baseline reproduction and strong comparison",
            ),
            EvidenceGap(
                gap_id="g-mechanism",
                description="mechanism limitation and failure risk",
            ),
        ],
        search_queries=[
            SearchQuery(
                query_id="q-baseline",
                gap_id="g-baseline",
                query="baseline reproduction strong comparison",
            ),
            SearchQuery(
                query_id="q-mechanism",
                gap_id="g-mechanism",
                query="alternative mechanism limitation negative failure",
            ),
        ],
        success_criteria=["The comparison is reproducible."],
        risks=["A negative result may invalidate the proposed mechanism."],
    )


def test_role_classification_is_ordered_and_deduplicated() -> None:
    roles = adapter._roles_from_text(
        "baseline reproduction strong comparison negative failure alternative "
        "mechanism limitation gap"
    )
    assert roles == (
        "baseline",
        "strong_comparison",
        "risk",
        "parallel_method",
        "gap",
    )
    assert adapter._role_from_text("unclassified evidence") == "other"
    assert adapter._role_from_text("mechanism baseline") == "baseline"


def test_gap_and_retrieval_roles_are_derived_from_runtime_plan() -> None:
    state = cast(PaperAgentState, {"plan": _plan()})

    gap_roles = adapter._gap_roles(state)
    assert gap_roles == {
        "g-baseline": "baseline",
        "g-mechanism": "risk",
    }
    assert adapter._retrieval_roles(state, gap_roles) == (
        "baseline",
        "risk",
        "strong_comparison",
        "parallel_method",
        "gap",
    )
    assert adapter._gap_roles(cast(PaperAgentState, {})) == {}
    assert adapter._retrieval_roles(cast(PaperAgentState, {}), {}) == ()


def test_supplied_material_reviews_use_declared_roles_without_accepting_claims() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="Review supplied material roles.",
                user_material_refs=[
                    "Reference A [declared role: baseline]",
                    "Reference B [declared role: mechanism]",
                    "Reference C",
                ],
            )
        },
    )

    reviews = adapter._supplied_material_reviews(state, existing_count=0)
    assert [review.role for review in reviews] == [
        "baseline",
        "parallel_method",
        "other",
    ]
    assert all(review.source_type == "user_material" for review in reviews)
    assert all(review.source_is_supplied_material for review in reviews)
    assert all(review.identity_verified is False for review in reviews)
    assert all(review.accepted is False for review in reviews)
    assert reviews[0].core_evidence is True
    assert reviews[1].core_evidence is True
    assert reviews[2].core_evidence is False

    remaining = adapter._supplied_material_reviews(state, existing_count=1)
    assert len(remaining) == 2
    assert adapter._supplied_material_reviews(state, existing_count=3) == ()
    assert adapter._supplied_material_reviews(cast(PaperAgentState, {}), existing_count=0) == ()


@pytest.mark.parametrize(
    ("arm_type", "expected"),
    [
        (ExperimentArmType.BASELINE, "baseline"),
        (ExperimentArmType.FULL, "full"),
        (ExperimentArmType.SINGLE_MODULE, "single_module"),
        (ExperimentArmType.LEAVE_ONE_OUT, "interaction"),
        (ExperimentArmType.STRONG_COMPARISON, "strong_comparison"),
        (ExperimentArmType.INTERACTION, "interaction"),
        (ExperimentArmType.EFFICIENCY, "efficiency"),
        (ExperimentArmType.NEGATIVE_CONTROL, "negative_control"),
        (ExperimentArmType.OTHER, "feasibility"),
    ],
)
def test_arm_type_mapping(
    arm_type: ExperimentArmType,
    expected: str,
) -> None:
    assert adapter._arm_type(arm_type) == expected


def test_fact_partition_fallback_prefers_plan_then_request() -> None:
    planned = cast(PaperAgentState, {"plan": _plan()})
    partitions = adapter._fact_partitions(planned)
    assert partitions.verified == ()
    assert partitions.inferred == (
        "Evaluate an evidence-backed method.",
        "Use reproducible comparisons and explicit failure analysis.",
    )
    assert partitions.proposed == ()
    assert partitions.unknown == ("A negative result may invalidate the proposed mechanism.",)

    requested = cast(
        PaperAgentState,
        {"request": ResearchRequest(question="A user-declared research objective")},
    )
    request_partitions = adapter._fact_partitions(requested)
    assert request_partitions.verified == (
        "User-declared research objective: A user-declared research objective",
    )
    assert request_partitions.inferred == ()
