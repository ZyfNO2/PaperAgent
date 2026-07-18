from __future__ import annotations

import operator
from typing import Annotated, Any, cast

from pydantic import TypeAdapter
from typing_extensions import TypedDict

from paperagent.academic_methodology import MethodAuditReport
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceSynthesis,
    ExecutionMeta,
    FinalReport,
    MethodProposal,
    QualityDecision,
    ResearchPlan,
    ResearchRequest,
    RetrievalState,
    RunContext,
    TraceEvent,
)


class PaperAgentState(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
    retrieval: RetrievalState
    evidence: EvidenceBundle
    synthesis: EvidenceSynthesis | None
    method: MethodProposal | None
    methodology_audit: MethodAuditReport | None
    quality: QualityDecision | None
    report: FinalReport | None
    execution: ExecutionMeta
    trace: Annotated[list[TraceEvent], operator.add]


class StatePatch(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
    retrieval: RetrievalState
    evidence: EvidenceBundle
    synthesis: EvidenceSynthesis | None
    method: MethodProposal | None
    methodology_audit: MethodAuditReport | None
    quality: QualityDecision | None
    report: FinalReport | None
    execution: ExecutionMeta
    trace: list[TraceEvent]


_STATE_ADAPTER = TypeAdapter(PaperAgentState)


def apply_state_patch(state: PaperAgentState, patch: StatePatch) -> PaperAgentState:
    updated = cast(PaperAgentState, dict(state))
    for key, value in patch.items():
        if key == "trace":
            updated["trace"] = [*state.get("trace", []), *value]  # type: ignore[misc]
        else:
            updated[key] = value  # type: ignore[literal-required]
    return updated


def state_to_json(state: PaperAgentState) -> str:
    return _STATE_ADAPTER.dump_json(state).decode("utf-8")


def state_from_json(payload: str) -> PaperAgentState:
    return _STATE_ADAPTER.validate_json(payload)


def state_to_primitive(state: PaperAgentState) -> dict[str, Any]:
    return cast(dict[str, Any], _STATE_ADAPTER.dump_python(state, mode="json"))
