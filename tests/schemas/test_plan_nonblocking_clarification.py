from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.schemas.plan import EvidenceGap, ResearchPlan, SearchQuery


def _ready_plan(**updates: object) -> ResearchPlan:
    payload: dict[str, object] = {
        "status": "ready",
        "problem_statement": "Improve a lightweight detector without inventing deployment facts.",
        "scope": "Conditional method design with unresolved deployment constraints.",
        "evidence_gaps": [
            EvidenceGap(
                gap_id="GAP_BASELINE",
                description="baseline and strong comparison evidence",
            )
        ],
        "search_queries": [
            SearchQuery(
                query_id="Q_BASELINE",
                gap_id="GAP_BASELINE",
                query="lightweight aerial small object detection baseline comparison",
                source_types=["paper"],
            )
        ],
        "clarification_question": (
            "Which dataset, deployment device, and accuracy-latency priority should constrain the method?"
        ),
    }
    payload.update(updates)
    return ResearchPlan.model_validate(payload)


def test_ready_plan_allows_one_nonblocking_clarification_question() -> None:
    plan = _ready_plan()

    assert plan.status == "ready"
    assert plan.clarification_question is not None


def test_ready_plan_still_rejects_block_reason() -> None:
    with pytest.raises(ValidationError):
        _ready_plan(block_reason="not compatible with ready")
