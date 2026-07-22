from __future__ import annotations

from paperagent.nodes.report import _fallback_report
from paperagent.schemas import FinalOutcome


def test_fallback_report_is_terminal_and_actionable_without_llm_output() -> None:
    outcome = FinalOutcome(
        execution_status="failed",
        scientific_verdict="NOT_EVALUATED",
        quality_route="blocked",
        report_status="blocked",
        blocker_code="METHOD_CANONICALIZATION_FAILED",
        reason_codes=["METHOD_CANONICALIZATION_FAILED"],
    )

    report = _fallback_report({}, outcome)  # type: ignore[arg-type]

    assert report.status == "blocked"
    assert report.limitations
    assert report.next_actions
    assert report.evidence_ids == []
