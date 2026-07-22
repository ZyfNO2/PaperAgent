from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from paperagent.nodes.evidence_synthesis import evidence_synthesis_node
from paperagent.nodes.human_review import human_review_node
from paperagent.nodes.intake import intake_node
from paperagent.nodes.method_design import method_design_node
from paperagent.nodes.methodology_audit import methodology_audit_node
from paperagent.nodes.persist import persist_node
from paperagent.nodes.planning import planning_node, planning_route
from paperagent.nodes.quality_gate import quality_gate_node, quality_route
from paperagent.nodes.readiness_preflight import (
    readiness_preflight_node,
    readiness_preflight_route,
)
from paperagent.nodes.report import report_node
from paperagent.outcome import derive_final_outcome
from paperagent.retrieval.graph import build_retrieval_graph
from paperagent.runtime import get_services
from paperagent.schemas import EvidenceBundle, QualityDecision, ResearchPlan, RetrievalState
from paperagent.state import PaperAgentState
from paperagent.telemetry import make_event


def _continue_unless_failed(state: PaperAgentState) -> str:
    execution = state.get("execution")
    return "blocked" if execution is not None and execution.status == "failed" else "continue"


def _after_retrieval(state: PaperAgentState) -> str:
    execution = state.get("execution")
    if execution is not None and execution.status == "failed":
        return "blocked"
    quality = state.get("quality")
    if quality is not None and quality.verdict == "blocked":
        return "blocked"
    return "continue"


def _retrieval_exhaustion_quality(
    plan: ResearchPlan,
    evidence: EvidenceBundle,
    retrieval: RetrievalState,
) -> QualityDecision | None:
    missing_gap_ids = [
        gap.gap_id
        for gap in plan.evidence_gaps
        if gap.required and evidence.coverage_by_gap.get(gap.gap_id, 0) < gap.minimum_accepted_items
    ]
    exhausted = retrieval.budget_exhausted or retrieval.round >= retrieval.max_rounds
    if not missing_gap_ids or not exhausted:
        return None
    if evidence.accepted_ids:
        return QualityDecision(
            verdict="repair_retrieval",
            reason_codes=[
                "Q_RETRIEVAL_BUDGET_EXHAUSTED",
                "Q_PARTIAL_EVIDENCE_COVERAGE",
            ],
            repair_target="retrieval",
            missing_gap_ids=missing_gap_ids,
        )
    return QualityDecision(
        verdict="blocked",
        reason_codes=[
            "Q_RETRIEVAL_BUDGET_EXHAUSTED",
            "Q_INSUFFICIENT_COVERAGE",
        ],
        missing_gap_ids=missing_gap_ids,
    )


def build_graph(*, checkpointer: Any | None = None) -> Any:
    retrieval = build_retrieval_graph()

    async def retrieval_subgraph_node(
        state: PaperAgentState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        result = await retrieval.ainvoke(state, config)
        prior_trace_count = len(state.get("trace", []))
        trace = list(result.get("trace", [])[prior_trace_count:])
        retrieval_state = result["retrieval"]
        evidence = result.get("evidence", state.get("evidence"))
        plan = state.get("plan")
        quality = None
        final_outcome = None
        if plan is not None and evidence is not None:
            quality = _retrieval_exhaustion_quality(plan, evidence, retrieval_state)
            if quality is not None and quality.verdict == "blocked":
                outcome_state: PaperAgentState = {
                    **state,
                    "retrieval": retrieval_state,
                    "evidence": evidence,
                    "evidence_ledger": result.get(
                        "evidence_ledger",
                        state.get("evidence_ledger"),
                    ),
                    "quality": quality,
                    "execution": result["execution"],
                }
                final_outcome = derive_final_outcome(outcome_state)
                trace.append(
                    make_event(
                        get_services(config),
                        outcome_state,
                        node="evidence_quality_gate_node",
                        event_type="route.decided",
                        status="decided",
                        route=quality.verdict,
                        output_payload={
                            "quality": quality,
                            "final_outcome": final_outcome,
                        },
                    )
                )
        return {
            "retrieval": retrieval_state,
            "research_contract": result.get(
                "research_contract",
                state.get("research_contract"),
            ),
            "lexical_assessments": result.get(
                "lexical_assessments",
                state.get("lexical_assessments", []),
            ),
            "relevance_assessments": result.get(
                "relevance_assessments",
                state.get("relevance_assessments", []),
            ),
            "gap_support_assessments": result.get(
                "gap_support_assessments",
                state.get("gap_support_assessments", []),
            ),
            "evidence_ledger": result.get(
                "evidence_ledger",
                state.get("evidence_ledger"),
            ),
            "evidence": evidence,
            "quality": quality,
            "final_outcome": final_outcome,
            "execution": result["execution"],
            "trace": trace,
        }

    builder = StateGraph(PaperAgentState)
    builder.add_node("intake_node", intake_node)
    builder.add_node("readiness_preflight_node", readiness_preflight_node)
    builder.add_node("planning_node", planning_node)
    builder.add_node("human_review_node", human_review_node)
    builder.add_node("retrieval_subgraph", retrieval_subgraph_node)
    builder.add_node("evidence_synthesis_node", evidence_synthesis_node)
    builder.add_node("method_design_node", method_design_node)
    builder.add_node("methodology_audit_node", methodology_audit_node)
    builder.add_node("quality_gate_node", quality_gate_node)
    builder.add_node("report_node", report_node)
    builder.add_node("persist_node", persist_node)

    builder.add_edge(START, "intake_node")
    builder.add_edge("intake_node", "readiness_preflight_node")
    builder.add_conditional_edges(
        "readiness_preflight_node",
        readiness_preflight_route,
        {
            "continue": "planning_node",
            "terminal": "report_node",
        },
    )
    builder.add_conditional_edges(
        "planning_node",
        planning_route,
        {
            "ready": "retrieval_subgraph",
            "need_human": "human_review_node",
            "blocked": "report_node",
        },
    )
    builder.add_edge("human_review_node", "planning_node")
    builder.add_conditional_edges(
        "retrieval_subgraph",
        _after_retrieval,
        {
            "continue": "evidence_synthesis_node",
            "blocked": "report_node",
        },
    )
    builder.add_conditional_edges(
        "evidence_synthesis_node",
        _continue_unless_failed,
        {"continue": "method_design_node", "blocked": "report_node"},
    )
    builder.add_conditional_edges(
        "method_design_node",
        _continue_unless_failed,
        {"continue": "methodology_audit_node", "blocked": "report_node"},
    )
    builder.add_edge("methodology_audit_node", "quality_gate_node")
    builder.add_conditional_edges(
        "quality_gate_node",
        quality_route,
        {
            "pass": "report_node",
            "repair_retrieval": "retrieval_subgraph",
            "repair_method": "method_design_node",
            "human_review": "human_review_node",
            "blocked": "report_node",
        },
    )
    builder.add_edge("report_node", "persist_node")
    builder.add_edge("persist_node", END)
    return builder.compile(checkpointer=checkpointer)
