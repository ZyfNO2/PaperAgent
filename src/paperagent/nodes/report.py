from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
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
    scenario = get_task_scenario(config, "report")
    if scenario == "happy_path" and (
        (quality and quality.verdict == "blocked")
        or (execution and execution.status in {"failed", "blocked"})
        or (plan and plan.status == "blocked")
    ):
        scenario = "blocked"

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

    method = state.get("method")
    patch, result = await call_structured(
        state=state,
        config=config,
        node=NODE,
        task="report",
        schema=FinalReport,
        scenario=scenario,
        user_payload={
            "quality": quality.model_dump(mode="json") if quality else {"verdict": "blocked"},
            "accepted_evidence_ids": sorted(accepted),
            "method_status": method.status if method is not None else None,
        },
        semantic_validate=validate,
    )
    if result is not None:
        patch["report"] = result
    return patch
