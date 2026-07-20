from __future__ import annotations

from paperagent.academic_methodology import AuditVerdict
from paperagent.schemas import FinalOutcome, TraceAuditResult, TraceInvariantResult
from paperagent.state import PaperAgentState
from paperagent.telemetry import hash_payload


def _next_actions(state: PaperAgentState, reason_codes: list[str]) -> list[str]:
    actions: list[str] = []
    quality = state.get("quality")
    if quality is not None:
        if quality.missing_gap_ids:
            actions.append(
                "Retrieve and validate evidence for gaps: " + ", ".join(quality.missing_gap_ids)
            )
        if quality.invalid_evidence_ids:
            actions.append(
                "Remove or replace invalid evidence references: "
                + ", ".join(quality.invalid_evidence_ids)
            )
    if any("METHODOLOGY" in code or "METHOD" in code for code in reason_codes):
        actions.append("Repair the methodology contract and rerun the canonical audit.")
    if any("RETRIEVAL" in code or "GAP" in code for code in reason_codes):
        actions.append("Run a focused retrieval round with stricter relevance and gap binding.")
    if "Q_HUMAN_DECISION_REQUIRED" in reason_codes:
        actions.append("Resolve the recorded human-review question before scientific acceptance.")
    if not actions:
        actions.append("Resolve the blocking contract evidence and rerun the workflow.")
    return actions


def _outcome(
    state: PaperAgentState,
    *,
    execution_status: str,
    scientific_verdict: str,
    report_status: str,
    reason_codes: list[str],
    blocker_code: str | None,
    recommended_next_actions: list[str],
) -> FinalOutcome:
    quality = state.get("quality")
    audit = state.get("methodology_audit")
    ledger = state.get("evidence_ledger")
    quality_route = quality.verdict if quality is not None else "blocked"
    return FinalOutcome.model_validate(
        {
            "execution_status": execution_status,
            "scientific_verdict": scientific_verdict,
            "quality_route": quality_route,
            "report_status": report_status,
            "reason_codes": reason_codes,
            "blocker_code": blocker_code,
            "missing_gap_ids": (list(quality.missing_gap_ids) if quality is not None else []),
            "invalid_evidence_ids": (
                list(quality.invalid_evidence_ids) if quality is not None else []
            ),
            "methodology_audit_fingerprint": (
                audit.plan_fingerprint if audit is not None else None
            ),
            "evidence_ledger_fingerprint": (
                hash_payload(ledger.model_dump(mode="json")) if ledger is not None else None
            ),
            "recommended_next_actions": recommended_next_actions,
            "pilot_recommended": (quality.pilot_recommended if quality is not None else False),
            "pilot_scope": (quality.pilot_scope if quality is not None else None),
        }
    )


def derive_final_outcome(state: PaperAgentState) -> FinalOutcome:
    execution = state.get("execution")
    quality = state.get("quality")
    plan = state.get("plan")
    audit = state.get("methodology_audit")
    readiness = state.get("scientific_readiness")
    reason_codes = list(quality.reason_codes) if quality is not None else []
    if execution is not None and execution.status == "failed":
        error_code = (
            execution.last_error.code if execution.last_error is not None else "EXECUTION_FAILED"
        )
        return _outcome(
            state,
            execution_status="failed",
            scientific_verdict="NOT_EVALUATED",
            report_status="blocked",
            reason_codes=[error_code],
            blocker_code=error_code,
            recommended_next_actions=[],
        )
    if readiness is not None and readiness.explicit_evaluation_protocol_invalid:
        reason = "Q_EXPLICIT_EVALUATION_PROTOCOL_INVALID"
        return _outcome(
            state,
            execution_status="succeeded",
            scientific_verdict="NO_GO",
            report_status="completed",
            reason_codes=reason_codes or [reason],
            blocker_code=reason,
            recommended_next_actions=[],
        )
    if (
        readiness is not None
        and readiness.declared_ready
        and quality is not None
        and quality.verdict == "pass"
    ):
        return _outcome(
            state,
            execution_status="succeeded",
            scientific_verdict="GO",
            report_status="completed",
            reason_codes=reason_codes,
            blocker_code=None,
            recommended_next_actions=[],
        )
    if plan is None or plan.status == "blocked":
        reason = (plan.block_reason if plan is not None else None) or "PLAN_NOT_AVAILABLE"
        return _outcome(
            state,
            execution_status="blocked",
            scientific_verdict="NOT_EVALUATED",
            report_status="blocked",
            reason_codes=[reason],
            blocker_code=reason,
            recommended_next_actions=[],
        )
    if quality is None:
        return _outcome(
            state,
            execution_status="blocked",
            scientific_verdict="NOT_EVALUATED",
            report_status="blocked",
            reason_codes=["QUALITY_NOT_EVALUATED"],
            blocker_code="QUALITY_NOT_EVALUATED",
            recommended_next_actions=[],
        )
    if audit is not None and audit.verdict is AuditVerdict.NO_GO:
        return _outcome(
            state,
            execution_status="succeeded",
            scientific_verdict="NO_GO",
            report_status="completed",
            reason_codes=reason_codes,
            blocker_code=reason_codes[0] if reason_codes else None,
            recommended_next_actions=[],
        )
    if quality.verdict == "pass":
        return _outcome(
            state,
            execution_status="succeeded",
            scientific_verdict="GO",
            report_status="completed",
            reason_codes=reason_codes,
            blocker_code=None,
            recommended_next_actions=[],
        )
    return _outcome(
        state,
        execution_status=("blocked" if quality.verdict == "human_review" else "succeeded"),
        scientific_verdict="REVISE",
        report_status="completed",
        reason_codes=reason_codes,
        blocker_code=reason_codes[0] if reason_codes else None,
        recommended_next_actions=_next_actions(state, reason_codes),
    )


def _report_evidence_ids(state: PaperAgentState) -> set[str]:
    report = state.get("report")
    if report is None:
        return set()
    values = set(report.evidence_ids)
    for claim in [*report.verified_findings, *report.inferred_findings]:
        values.update(claim.evidence_ids)
    return values


def audit_state_consistency(state: PaperAgentState) -> TraceAuditResult:
    results: list[TraceInvariantResult] = []

    def record(
        invariant_id: str,
        passed: bool,
        details: str | None = None,
    ) -> None:
        results.append(
            TraceInvariantResult(
                invariant_id=invariant_id,
                passed=passed,
                details=details,
            )
        )

    evidence = state.get("evidence")
    ledger = state.get("evidence_ledger")
    report = state.get("report")
    outcome = state.get("final_outcome")
    quality = state.get("quality")
    audit = state.get("methodology_audit")
    readiness = state.get("scientific_readiness")
    readiness_terminal = bool(
        readiness is not None
        and (readiness.explicit_evaluation_protocol_invalid or readiness.declared_ready)
    )

    if evidence is not None and ledger is not None:
        record(
            "EVIDENCE_ACCEPTANCE_MATCHES_LEDGER",
            set(evidence.accepted_ids) == set(ledger.accepted_ids),
            "EvidenceBundle.accepted_ids must be derived from EvidenceLedger.",
        )
        record(
            "GAP_COVERAGE_MATCHES_LEDGER",
            evidence.coverage_by_gap == ledger.coverage_by_gap,
            "Gap coverage must be independently reproducible from accepted bindings.",
        )
        unknown_report_ids = _report_evidence_ids(state) - set(ledger.accepted_ids)
        record(
            "REPORT_REFERENCES_ACCEPTED_EVIDENCE",
            not unknown_report_ids,
            (
                f"unknown or rejected report evidence IDs: {sorted(unknown_report_ids)}"
                if unknown_report_ids
                else None
            ),
        )
    else:
        record(
            "EVIDENCE_LEDGER_PRESENT",
            bool(
                outcome is not None
                and (outcome.scientific_verdict == "NOT_EVALUATED" or readiness_terminal)
            ),
            (
                "Evaluated scientific outcomes require an evidence ledger unless the "
                "decision is explicitly limited to a user-declaration readiness preflight."
            ),
        )

    if outcome is not None and report is not None:
        record(
            "REPORT_STATUS_MATCHES_FINAL_OUTCOME",
            report.status == outcome.report_status,
            f"report={report.status}, outcome={outcome.report_status}",
        )
        record(
            "REVISE_HAS_NEXT_ACTIONS",
            outcome.scientific_verdict != "REVISE" or bool(report.next_actions),
            "REVISE reports must contain actionable repair steps.",
        )
    else:
        record(
            "FINAL_OUTCOME_AND_REPORT_PRESENT",
            False,
            "final outcome and report are required",
        )

    if outcome is not None and outcome.scientific_verdict == "GO":
        record(
            "GO_REQUIRES_QUALITY_PASS",
            quality is not None and quality.verdict == "pass",
            "GO cannot be produced from a repair or blocked quality route.",
        )
    else:
        record("GO_REQUIRES_QUALITY_PASS", True)

    if outcome is not None and outcome.scientific_verdict == "NO_GO":
        record(
            "NO_GO_REQUIRES_METHOD_AUDIT",
            bool(
                (audit is not None and audit.verdict is AuditVerdict.NO_GO)
                or (readiness is not None and readiness.explicit_evaluation_protocol_invalid)
            ),
            (
                "Scientific NO_GO must come from the canonical methodology audit or an "
                "explicitly declared invalid evaluation protocol."
            ),
        )
    else:
        record("NO_GO_REQUIRES_METHOD_AUDIT", True)

    quality_route_nodes = {
        "quality_gate_node",
        "evidence_quality_gate_node",
        "readiness_preflight_node",
    }
    route_events = [
        event.route
        for event in state.get("trace", [])
        if event.node in quality_route_nodes and event.event_type == "route.decided"
    ]
    record(
        "QUALITY_ROUTE_RECORDED",
        quality is None or bool(route_events and route_events[-1] == quality.verdict),
        f"recorded routes={route_events}, quality={quality.verdict if quality else None}",
    )

    error_codes = [result.invariant_id for result in results if not result.passed]
    return TraceAuditResult(
        passed=not error_codes,
        results=results,
        error_codes=error_codes,
    )


__all__ = ["audit_state_consistency", "derive_final_outcome"]
