from __future__ import annotations

import operator
from typing import Annotated, Any, cast

from pydantic import TypeAdapter
from typing_extensions import TypedDict

from paperagent.academic_methodology import MethodAuditReport
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceLedger,
    EvidenceSynthesis,
    ExecutionMeta,
    FinalOutcome,
    FinalReport,
    GapSupportAssessment,
    LexicalRelevanceAssessment,
    MethodProposal,
    QualityDecision,
    RelevanceAssessment,
    ResearchContract,
    ResearchPlan,
    ResearchRequest,
    RetrievalState,
    RunContext,
    TraceAuditResult,
    TraceEvent,
)


class PaperAgentState(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
    research_contract: ResearchContract | None
    retrieval: RetrievalState
    evidence: EvidenceBundle
    lexical_assessments: list[LexicalRelevanceAssessment]
    relevance_assessments: list[RelevanceAssessment]
    gap_support_assessments: list[GapSupportAssessment]
    evidence_ledger: EvidenceLedger | None
    synthesis: EvidenceSynthesis | None
    method: MethodProposal | None
    methodology_audit: MethodAuditReport | None
    quality: QualityDecision | None
    final_outcome: FinalOutcome | None
    report: FinalReport | None
    trace_audit: TraceAuditResult | None
    execution: ExecutionMeta
    trace: Annotated[list[TraceEvent], operator.add]


class StatePatch(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
    research_contract: ResearchContract | None
    retrieval: RetrievalState
    evidence: EvidenceBundle
    lexical_assessments: list[LexicalRelevanceAssessment]
    relevance_assessments: list[RelevanceAssessment]
    gap_support_assessments: list[GapSupportAssessment]
    evidence_ledger: EvidenceLedger | None
    synthesis: EvidenceSynthesis | None
    method: MethodProposal | None
    methodology_audit: MethodAuditReport | None
    quality: QualityDecision | None
    final_outcome: FinalOutcome | None
    report: FinalReport | None
    trace_audit: TraceAuditResult | None
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
