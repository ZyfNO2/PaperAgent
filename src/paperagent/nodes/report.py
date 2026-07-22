from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured, execution_with
from paperagent.outcome import derive_final_outcome
from paperagent.runtime import get_task_scenario
from paperagent.schemas import FinalOutcome, FinalReport, ReportClaim
from paperagent.state import PaperAgentState, StatePatch

NODE = "report_node"


def _fallback_report(state: PaperAgentState, final_outcome: FinalOutcome) -> FinalReport:
    """Build a provenance-safe terminal report when report prose generation fails."""

    evidence = state.get("evidence")
    accepted = set(evidence.accepted_ids) if evidence is not None else set()
    synthesis = state.get("synthesis")
    verified_findings: list[ReportClaim] = []
    if synthesis is not None:
        for claim in synthesis.verified_findings:
            evidence_ids = [item for item in claim.evidence_ids if item in accepted]
            verified_findings.append(ReportClaim(text=claim.text, evidence_ids=evidence_ids))
    method = state.get("method")
    limitations = list(synthesis.limitations) if synthesis is not None else []
    fallback_note = (
        "Report prose was generated deterministically because the LLM report call did not "
        "complete; scientific fields are copied only from validated state artifacts."
    )
    if fallback_note not in limitations:
        limitations.append(fallback_note)
    next_actions = list(final_outcome.recommended_next_actions)
    if final_outcome.report_status == "blocked" and not next_actions:
        next_actions.append(
            "Resolve the recorded blocker and rerun from the failed node before using the method."
        )
    verdict = final_outcome.scientific_verdict.replace("_", " ")
    return FinalReport(
        status=final_outcome.report_status,
        executive_summary=(
            f"Deterministic terminal report: scientific verdict {verdict}; "
            f"execution status {final_outcome.execution_status}."
        ),
        verified_findings=verified_findings,
        inferred_findings=[],
        proposed_method=(method.problem_method_insight if method is not None else None),
        experiment_plan=None,
        limitations=limitations,
        next_actions=next_actions,
        evidence_ids=sorted(
            {evidence_id for claim in verified_findings for evidence_id in claim.evidence_ids}
        ),
    )


async def report_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    evidence = state.get("evidence")
    accepted = set(evidence.accepted_ids) if evidence else set()
    quality = state.get("quality")
    execution = state.get("execution")
    plan = state.get("plan")
    final_outcome = state.get("final_outcome") or derive_final_outcome(state)
    scenario = get_task_scenario(config, "report")
    if scenario == "happy_path" and (
        final_outcome.report_status != "completed"
        or (execution and execution.status in {"failed", "blocked"})
        or (plan and plan.status == "blocked")
    ):
        scenario = "blocked"

    def transform(report: FinalReport) -> FinalReport:
        next_actions = list(report.next_actions)
        for action in final_outcome.recommended_next_actions:
            if action not in next_actions:
                next_actions.append(action)
        return report.model_copy(
            update={
                "status": final_outcome.report_status,
                "next_actions": next_actions,
            }
        )

    def validate(report: FinalReport) -> None:
        unknown = set(report.evidence_ids) - accepted
        for claim in [*report.verified_findings, *report.inferred_findings]:
            unknown.update(set(claim.evidence_ids) - accepted)
        if unknown:
            raise NodeError(
                code="SEMANTIC_UNKNOWN_EVIDENCE_ID",
                message=f"report referenced unknown evidence IDs: {sorted(unknown)}",
                node=NODE,
            )
        if report.status != final_outcome.report_status:
            raise NodeError(
                code="REPORT_OUTCOME_STATUS_MISMATCH",
                message=(
                    f"report status {report.status!r} does not match final outcome "
                    f"{final_outcome.report_status!r}"
                ),
                node=NODE,
            )
        if final_outcome.scientific_verdict == "REVISE" and not report.next_actions:
            raise NodeError(
                code="REVISE_REPORT_MISSING_NEXT_ACTIONS",
                message="REVISE report requires actionable next steps",
                node=NODE,
            )

    method = state.get("method")
    patch, result = await call_structured(
        state=state,
        config=config,
        node=NODE,
        task="report",
        schema=FinalReport,
        scenario=scenario,
        user_payload={
            "final_outcome": final_outcome.model_dump(mode="json"),
            "quality": quality.model_dump(mode="json") if quality else {"verdict": "blocked"},
            "accepted_evidence_ids": sorted(accepted),
            "method_status": method.status if method is not None else None,
        },
        transform=transform,
        semantic_validate=validate,
    )
    patch["final_outcome"] = final_outcome
    if result is not None:
        patch["report"] = result
    else:
        patch["report"] = _fallback_report(state, final_outcome)
        # The failed prose call is observable in trace, but a deterministic report recovers the
        # presentation layer. Preserve the upstream execution status and clear this local error.
        patch["execution"] = execution_with(
            state,
            node=NODE,
            llm_increment=1,
            error=None,
        )
    return patch
