from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.schemas import EvidenceSynthesis
from paperagent.state import PaperAgentState, StatePatch

NODE = "evidence_synthesis_node"


async def evidence_synthesis_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    plan = state.get("plan")
    evidence = state.get("evidence")
    if plan is None or evidence is None:
        raise ValueError("plan and evidence are required")
    accepted_ids = set(evidence.accepted_ids)

    def validate(synthesis: EvidenceSynthesis) -> None:
        unknown = synthesis.referenced_evidence_ids() - accepted_ids
        if unknown:
            raise NodeError(
                code="SEMANTIC_UNKNOWN_EVIDENCE_ID",
                message=f"synthesis referenced unknown evidence IDs: {sorted(unknown)}",
                node=NODE,
            )

    patch, result = await call_structured(
        state=state,
        config=config,
        node=NODE,
        task="evidence_synthesis",
        schema=EvidenceSynthesis,
        user_payload={
            "plan": {
                "problem_statement": plan.problem_statement,
                "evidence_gap_ids": [gap.gap_id for gap in plan.evidence_gaps],
            },
            "accepted_evidence": [
                item.model_dump(mode="json") for item in evidence.accepted_items()
            ],
            "coverage_by_gap": evidence.coverage_by_gap,
            "conflicts": [item.model_dump(mode="json") for item in evidence.conflicts],
        },
        semantic_validate=validate,
    )
    if result is not None:
        patch["synthesis"] = result
    return patch
