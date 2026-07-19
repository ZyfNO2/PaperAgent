from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.outcome import derive_final_outcome
from paperagent.runtime import get_task_scenario
from paperagent.schemas import FinalReport
from paperagent.state import PaperAgentState, StatePatch

NODE = "report_node"


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
    return patch
