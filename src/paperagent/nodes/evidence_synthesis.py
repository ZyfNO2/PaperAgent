from __future__ import annotations

from types import GenericAlias
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, create_model

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.schemas import EvidenceSynthesis
from paperagent.state import PaperAgentState, StatePatch

NODE = "evidence_synthesis_node"


def _literal_type(values: tuple[str, ...]) -> Any:
    if not values:
        raise ValueError("at least one allowed value is required")
    return Literal.__getitem__(values)  # type: ignore[attr-defined]


def _list_type(item_type: Any) -> Any:
    return GenericAlias(list, item_type)


def _constrained_synthesis_schema(
    *,
    accepted_evidence_ids: tuple[str, ...],
    gap_ids: tuple[str, ...],
) -> type[BaseModel]:
    """Build a per-run schema that forbids invented evidence and gap identifiers."""

    evidence_id_type = _literal_type(accepted_evidence_ids)
    gap_id_type = _literal_type(gap_ids)
    evidence_id_list = _list_type(evidence_id_type)

    claim = create_model(
        "ConstrainedEvidenceSynthesisClaim",
        claim_id=(str, ...),
        text=(str, ...),
        evidence_ids=(evidence_id_list, ...),
    )
    gap = create_model(
        "ConstrainedEvidenceSynthesisGap",
        gap_id=(gap_id_type, ...),
        status=(Literal["supported", "partial", "unsupported", "conflicted"], ...),
        evidence_ids=(evidence_id_list, ...),
        summary=(str, ...),
        limitations=(list[str], Field(default_factory=list)),
    )
    conflict = create_model(
        "ConstrainedEvidenceSynthesisConflict",
        conflict_id=(str, ...),
        evidence_ids=(evidence_id_list, ...),
        summary=(str, ...),
    )
    return create_model(
        "ConstrainedEvidenceSynthesis",
        schema_version=(Literal["0.1"], "0.1"),
        gap_assessments=(_list_type(gap), ...),
        verified_findings=(_list_type(claim), ...),
        conflicts=(_list_type(conflict), ...),
        feasibility=(
            Literal["feasible", "partially_feasible", "not_feasible", "unknown"],
            ...,
        ),
        limitations=(list[str], ...),
    )


def _to_evidence_synthesis(value: BaseModel) -> EvidenceSynthesis:
    return EvidenceSynthesis.model_validate(value.model_dump(mode="json"))


async def evidence_synthesis_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    plan = state.get("plan")
    evidence = state.get("evidence")
    if plan is None or evidence is None:
        raise ValueError("plan and evidence are required")
    accepted_ids = tuple(sorted(evidence.accepted_ids))
    if not accepted_ids:
        raise ValueError("accepted evidence is required for evidence synthesis")
    gap_ids = tuple(gap.gap_id for gap in plan.evidence_gaps)
    schema = _constrained_synthesis_schema(
        accepted_evidence_ids=accepted_ids,
        gap_ids=gap_ids,
    )
    accepted_id_set = set(accepted_ids)

    def validate(synthesis: EvidenceSynthesis) -> None:
        unknown = synthesis.referenced_evidence_ids() - accepted_id_set
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
        schema=schema,
        transform=_to_evidence_synthesis,
        user_payload={
            "plan": {
                "problem_statement": plan.problem_statement,
                "evidence_gap_ids": list(gap_ids),
            },
            "allowed_evidence_ids": list(accepted_ids),
            "identifier_rule": (
                "Copy evidence_id values exactly from allowed_evidence_ids. "
                "Do not create, expand, hash, abbreviate, or rewrite identifiers."
            ),
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
