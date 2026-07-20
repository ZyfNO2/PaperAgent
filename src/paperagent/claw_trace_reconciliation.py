from __future__ import annotations

from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace
from paperagent.state import PaperAgentState


def reconcile_ledger_relevance(
    state: PaperAgentState,
    trace: AcademicTailoringRunTrace,
) -> AcademicTailoringRunTrace:
    """Reconcile accepted Ledger relevance checks into the normalized trace.

    The Evidence Ledger can contain an auditable ``relevance_passed`` checklist
    even when the transient ``relevance_assessments`` list no longer contains a
    separate row for the same evidence item. Only an accepted ledger entry with
    an accepted gap support and an explicit positive relevance check can fill
    that trace field. Identity verification, evidence role, gap binding, and
    acceptance remain unchanged.
    """

    ledger = state.get("evidence_ledger")
    if ledger is None:
        return trace

    entries = {item.evidence_id: item for item in ledger.entries}
    reconciled = []
    changed = False
    for review in trace.evidence_reviews:
        entry = entries.get(review.evidence_id)
        ledger_relevance_passed = bool(
            review.accepted
            and entry is not None
            and entry.accepted
            and any(
                support.decision == "accept"
                and support.checklist_results.get("relevance_passed") is True
                for support in entry.gap_supports
            )
        )
        if ledger_relevance_passed and (
            not review.relevance_reviewed or not review.relevance_passed
        ):
            review = review.model_copy(
                update={
                    "relevance_reviewed": True,
                    "relevance_passed": True,
                }
            )
            changed = True
        reconciled.append(review)

    if not changed:
        return trace
    return trace.model_copy(update={"evidence_reviews": tuple(reconciled)})


__all__ = ["reconcile_ledger_relevance"]
