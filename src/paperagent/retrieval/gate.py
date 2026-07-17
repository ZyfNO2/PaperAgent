from __future__ import annotations

from paperagent.schemas import EvidenceBundle, RetrievalState
from paperagent.state import PaperAgentState


def retrieval_gate(state: PaperAgentState) -> str:
    plan = state.get("plan")
    if plan is None:
        raise ValueError("plan is required")
    retrieval = state.get("retrieval", RetrievalState())
    evidence = state.get("evidence", EvidenceBundle())
    enough = all(
        evidence.coverage_by_gap.get(gap.gap_id, 0) >= gap.minimum_accepted_items
        for gap in plan.evidence_gaps
        if gap.required
    )
    if enough:
        return "enough"
    if retrieval.round < retrieval.max_rounds and not retrieval.budget_exhausted:
        return "retry_under_budget"
    return "budget_exhausted"
