from __future__ import annotations

import re

from langchain_core.runnables import RunnableConfig

from paperagent.academic_methodology import AuditVerdict, audit_method_plan
from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_option, get_services
from paperagent.schemas import EvidenceBundle, QualityDecision, RetrievalState
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "quality_gate_node"


def _has_threshold(text: str) -> bool:
    return bool(re.search(r"(?:\d+(?:\.\d+)?|>=|<=|>|<)", text))


def _audit_reason_code(check_id: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", check_id.upper()).strip("_")
    return f"Q_METHOD_AUDIT_{normalized}"


def evaluate_quality(state: PaperAgentState) -> QualityDecision:
    plan = state.get("plan")
    if plan is None:
        return QualityDecision(verdict="blocked", reason_codes=["Q_MISSING_PLAN"])
    evidence = state.get("evidence", EvidenceBundle())
    retrieval = state.get("retrieval", RetrievalState())
    missing = [
        gap.gap_id
        for gap in plan.evidence_gaps
        if gap.required and evidence.coverage_by_gap.get(gap.gap_id, 0) < gap.minimum_accepted_items
    ]
    if missing:
        if retrieval.round < retrieval.max_rounds and not retrieval.budget_exhausted:
            return QualityDecision(
                verdict="repair_retrieval",
                reason_codes=["Q_MISSING_REQUIRED_GAP", "Q_INSUFFICIENT_COVERAGE"],
                repair_target="retrieval",
                missing_gap_ids=missing,
            )
        return QualityDecision(
            verdict="blocked",
            reason_codes=["Q_RETRIEVAL_BUDGET_EXHAUSTED"],
            missing_gap_ids=missing,
        )
    synthesis = state.get("synthesis")
    method = state.get("method")
    if synthesis is None or method is None:
        return QualityDecision(verdict="blocked", reason_codes=["Q_MISSING_ARTIFACT"])
    methodology_audit = state.get("methodology_audit")
    if methodology_audit is None:
        methodology_audit = audit_method_plan(method.methodology_plan)
    required_gap_ids = {gap.gap_id for gap in plan.evidence_gaps if gap.required}
    weak_gap_ids = sorted(
        assessment.gap_id
        for assessment in synthesis.gap_assessments
        if assessment.gap_id in required_gap_ids and assessment.status != "supported"
    )
    if weak_gap_ids:
        if retrieval.round < retrieval.max_rounds and not retrieval.budget_exhausted:
            return QualityDecision(
                verdict="repair_retrieval",
                reason_codes=["Q_SYNTHESIS_GAP_WEAK"],
                repair_target="retrieval",
                missing_gap_ids=weak_gap_ids,
            )
        return QualityDecision(
            verdict="blocked",
            reason_codes=["Q_RETRIEVAL_BUDGET_EXHAUSTED", "Q_SYNTHESIS_GAP_WEAK"],
            missing_gap_ids=weak_gap_ids,
        )
    accepted = set(evidence.accepted_ids)
    canonical_evidence_ids = {item.evidence_id for item in method.methodology_plan.evidence}
    invalid = (
        synthesis.referenced_evidence_ids() | set(method.evidence_ids) | canonical_evidence_ids
    ) - accepted
    execution = state.get("execution")
    run = state.get("run")
    max_repairs = run.budgets.max_method_repairs if run is not None else 1
    repair_count = execution.repair_count if execution else 0
    if invalid:
        if repair_count < max_repairs:
            return QualityDecision(
                verdict="repair_method",
                reason_codes=["Q_UNKNOWN_EVIDENCE_ID"],
                repair_target="method",
                invalid_evidence_ids=sorted(invalid),
            )
        return QualityDecision(
            verdict="blocked",
            reason_codes=["Q_REPAIR_BUDGET_EXHAUSTED", "Q_UNKNOWN_EVIDENCE_ID"],
            invalid_evidence_ids=sorted(invalid),
        )

    audit_failures = [
        _audit_reason_code(check_id) for check_id in methodology_audit.trace.failed_check_ids
    ]
    if methodology_audit.verdict is AuditVerdict.NO_GO:
        return QualityDecision(
            verdict="blocked",
            reason_codes=["Q_METHODOLOGY_NO_GO", *audit_failures],
        )
    if methodology_audit.verdict is AuditVerdict.REVISE:
        if repair_count < max_repairs:
            return QualityDecision(
                verdict="repair_method",
                reason_codes=["Q_METHODOLOGY_REVISE", *audit_failures],
                repair_target="method",
            )
        return QualityDecision(
            verdict="blocked",
            reason_codes=[
                "Q_REPAIR_BUDGET_EXHAUSTED",
                "Q_METHODOLOGY_REVISE",
                *audit_failures,
            ],
        )

    method_missing: list[str] = []
    if not method.baseline.name.strip():
        method_missing.append("Q_MISSING_BASELINE")
    if not _has_threshold(method.falsifiable_hypothesis):
        method_missing.append("Q_MISSING_HYPOTHESIS")
    if not method.minimum_key_experiment.metrics or not _has_threshold(
        method.minimum_key_experiment.success_threshold
    ):
        method_missing.append("Q_MISSING_EXPERIMENT")
    if not method.ablations:
        method_missing.append("Q_MISSING_ABLATION")
    if not method.stop_conditions:
        method_missing.append("Q_MISSING_STOP_CONDITION")
    if method_missing:
        if repair_count < max_repairs:
            return QualityDecision(
                verdict="repair_method",
                reason_codes=method_missing,
                repair_target="method",
            )
        return QualityDecision(
            verdict="blocked",
            reason_codes=["Q_REPAIR_BUDGET_EXHAUSTED", *method_missing],
        )
    if any("human decision required" in risk.lower() for risk in method.risks):
        return QualityDecision(
            verdict="human_review",
            reason_codes=["Q_HUMAN_DECISION_REQUIRED"],
            human_question="A human decision is required before continuing.",
        )
    return QualityDecision(verdict="pass", reason_codes=[])


async def quality_gate_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    decision = evaluate_quality(state)
    increment = 1 if decision.verdict == "repair_method" else 0
    trace = [
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.started",
            status="started",
        ),
        make_event(
            services,
            state,
            node=NODE,
            event_type="route.decided",
            status="decided",
            route=decision.verdict,
            output_payload=decision,
        ),
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.completed",
            status="completed",
            output_payload=decision,
        ),
    ]
    return {
        "quality": decision,
        "execution": execution_with(
            state,
            node=NODE,
            repair_increment=increment,
            repair_target=decision.repair_target,
        ),
        "trace": trace,
    }


def quality_route(state: PaperAgentState, config: RunnableConfig) -> str:
    quality = state.get("quality")
    if quality is None:
        raise ValueError("quality decision is required")
    if (
        quality.verdict == "human_review"
        and get_option(config, "human_review_policy", "interrupt") == "block"
    ):
        return "blocked"
    return quality.verdict
