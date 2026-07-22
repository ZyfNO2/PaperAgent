from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.nodes.evidence_synthesis import (
    _constrained_synthesis_schema,
    _to_evidence_synthesis,
)


def _payload(*, evidence_id: str, gap_id: str) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "gap_assessments": [
            {
                "gap_id": gap_id,
                "status": "supported",
                "evidence_ids": [evidence_id],
                "summary": "Supported by accepted evidence.",
                "limitations": [],
            }
        ],
        "verified_findings": [
            {
                "claim_id": "claim-1",
                "text": "A grounded finding.",
                "evidence_ids": [evidence_id],
            }
        ],
        "conflicts": [],
        "feasibility": "partially_feasible",
        "limitations": ["One bounded limitation."],
    }


def test_constrained_schema_accepts_exact_runtime_identifiers() -> None:
    schema = _constrained_synthesis_schema(
        accepted_evidence_ids=("ev-accepted",),
        gap_ids=("gap-accepted",),
    )

    constrained = schema.model_validate(_payload(evidence_id="ev-accepted", gap_id="gap-accepted"))
    synthesis = _to_evidence_synthesis(constrained)

    assert synthesis.referenced_evidence_ids() == {"ev-accepted"}
    assert synthesis.gap_assessments[0].gap_id == "gap-accepted"


def test_constrained_schema_rejects_invented_evidence_identifier() -> None:
    schema = _constrained_synthesis_schema(
        accepted_evidence_ids=("ev-accepted",),
        gap_ids=("gap-accepted",),
    )

    with pytest.raises(ValidationError):
        schema.model_validate(_payload(evidence_id="ev-invented", gap_id="gap-accepted"))


def test_constrained_schema_rejects_unknown_gap_identifier() -> None:
    schema = _constrained_synthesis_schema(
        accepted_evidence_ids=("ev-accepted",),
        gap_ids=("gap-accepted",),
    )

    with pytest.raises(ValidationError):
        schema.model_validate(_payload(evidence_id="ev-accepted", gap_id="gap-invented"))
