from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.schemas import MethodProposal
from paperagent.state import PaperAgentState, StatePatch

NODE = "method_design_node"


async def method_design_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    plan = state.get("plan")
    synthesis = state.get("synthesis")
    evidence = state.get("evidence")
    if plan is None or synthesis is None or evidence is None:
        raise ValueError("plan, synthesis and evidence are required")
    accepted_ids = set(evidence.accepted_ids)

    def validate(method: MethodProposal) -> None:
        canonical_evidence_ids = {item.evidence_id for item in method.methodology_plan.evidence}
        unknown = (set(method.evidence_ids) | canonical_evidence_ids) - accepted_ids
        if unknown:
            raise NodeError(
                code="SEMANTIC_UNKNOWN_EVIDENCE_ID",
                message=f"method referenced unknown evidence IDs: {sorted(unknown)}",
                node=NODE,
            )

    request = state.get("request")
    quality = state.get("quality")
    patch, result = await call_structured(
        state=state,
        config=config,
        node=NODE,
        task="method_design",
        schema=MethodProposal,
        user_payload={
            "problem_statement": plan.problem_statement,
            "verified_findings": [
                claim.model_dump(mode="json") for claim in synthesis.verified_findings
            ],
            "constraints": request.required_constraints if request is not None else [],
            "repair_reason": quality.reason_codes if quality is not None else None,
            "canonical_methodology_contract": {
                "required": True,
                "contract_version": "paperagent.method-plan.v0.9",
                "authoritative_audit": True,
            },
        },
        semantic_validate=validate,
    )
    if result is not None:
        patch["method"] = result
        patch["methodology_audit"] = None
    return patch
