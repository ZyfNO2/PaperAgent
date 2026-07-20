from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from paperagent.academic_methodology import ExperimentArmType
from paperagent.nodes.quality_gate import _production_pilot_recommendation
from paperagent.schemas import FinalOutcome, QualityDecision
from paperagent.state import PaperAgentState


def _decision(*, verdict: str = "repair_method", invalid: bool = False) -> QualityDecision:
    return QualityDecision(
        verdict=verdict,
        reason_codes=["Q_METHODOLOGY_REVISE"],
        repair_target="method" if verdict == "repair_method" else None,
        invalid_evidence_ids=["ev-invalid"] if invalid else [],
    )


def _state(
    *,
    baseline_evidence_id: str = "ev-base",
    comparator: str = "Method-B",
    include_pilot: bool = True,
) -> PaperAgentState:
    experiments = [
        SimpleNamespace(
            arm_type=ExperimentArmType.STRONG_COMPARISON,
            source_evidence_id="ev-strong",
            comparator=comparator,
            dataset="HeldOutSet",
            metrics=("F1",),
            stopping_criteria="stop when F1 gain is below 1%",
        )
    ]
    if include_pilot:
        experiments.append(
            SimpleNamespace(
                arm_type=ExperimentArmType.FULL,
                source_evidence_id="ev-base",
                comparator="Method-B",
                dataset="HeldOutSet",
                metrics=("F1", "latency"),
                stopping_criteria="stop when F1 gain is below 1%",
            )
        )
    plan = SimpleNamespace(
        baseline=SimpleNamespace(
            source_evidence_id=baseline_evidence_id,
            name="Method-A",
            dataset="HeldOutSet",
        ),
        modules=(SimpleNamespace(evidence_id="ev-module"),),
        experiments=tuple(experiments),
    )
    return cast(
        PaperAgentState,
        {
            "method": SimpleNamespace(methodology_plan=plan),
            "evidence_ledger": SimpleNamespace(
                accepted_ids=("ev-base", "ev-module", "ev-strong")
            ),
        },
    )


def test_production_quality_gate_emits_concrete_pilot_scope() -> None:
    recommended, scope = _production_pilot_recommendation(_state(), _decision())

    assert recommended is True
    assert scope is not None
    assert "dataset=HeldOutSet" in scope
    assert "metrics=F1, latency" in scope
    assert "comparator=Method-B" in scope
    assert "stop=stop when F1 gain is below 1%" in scope


@pytest.mark.parametrize(
    ("state", "decision"),
    [
        (_state(), _decision(verdict="pass")),
        (_state(), _decision(invalid=True)),
        (_state(baseline_evidence_id="ev-missing"), _decision()),
        (_state(comparator="unresolved before the pilot"), _decision()),
        (_state(include_pilot=False), _decision()),
    ],
)
def test_production_quality_gate_rejects_incomplete_pilot_contract(
    state: PaperAgentState,
    decision: QualityDecision,
) -> None:
    assert _production_pilot_recommendation(state, decision) == (False, None)


def test_final_outcome_accepts_only_structured_revise_pilot() -> None:
    outcome = FinalOutcome(
        execution_status="succeeded",
        scientific_verdict="REVISE",
        quality_route="repair_method",
        report_status="completed",
        reason_codes=["Q_METHODOLOGY_REVISE"],
        recommended_next_actions=["Run the bounded pilot."],
        pilot_recommended=True,
        pilot_scope="dataset=HeldOutSet; metrics=F1; comparator=Method-B; stop=F1 gain < 1%",
    )
    assert outcome.pilot_recommended is True

    with pytest.raises(ValidationError, match="pilot recommendation is only valid for REVISE"):
        FinalOutcome(
            execution_status="succeeded",
            scientific_verdict="GO",
            quality_route="pass",
            report_status="completed",
            pilot_recommended=True,
            pilot_scope="dataset=HeldOutSet",
        )

    with pytest.raises(ValidationError, match="pilot_recommended requires pilot_scope"):
        FinalOutcome(
            execution_status="succeeded",
            scientific_verdict="REVISE",
            quality_route="repair_method",
            report_status="completed",
            recommended_next_actions=["Run the bounded pilot."],
            pilot_recommended=True,
        )
