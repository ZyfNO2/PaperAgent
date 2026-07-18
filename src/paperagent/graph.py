from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from paperagent.nodes.evidence_synthesis import evidence_synthesis_node
from paperagent.nodes.human_review import human_review_node
from paperagent.nodes.intake import intake_node
from paperagent.nodes.method_design import method_design_node
from paperagent.nodes.persist import persist_node
from paperagent.nodes.planning import planning_node, planning_route
from paperagent.nodes.quality_gate import quality_gate_node, quality_route
from paperagent.nodes.report import report_node
from paperagent.retrieval.graph import build_retrieval_graph
from paperagent.state import PaperAgentState


def _continue_unless_failed(state: PaperAgentState) -> str:
    execution = state.get("execution")
    return "blocked" if execution is not None and execution.status == "failed" else "continue"


def build_graph(*, checkpointer: Any | None = None) -> Any:
    retrieval = build_retrieval_graph()

    async def retrieval_subgraph_node(
        state: PaperAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        result = await retrieval.ainvoke(state, config)
        prior_trace_count = len(state.get("trace", []))
        return {
            "retrieval": result["retrieval"],
            "evidence": result.get("evidence", state.get("evidence")),
            "execution": result["execution"],
            "trace": result.get("trace", [])[prior_trace_count:],
        }

    builder = StateGraph(PaperAgentState)
    builder.add_node("intake_node", intake_node)
    builder.add_node("planning_node", planning_node)
    builder.add_node("human_review_node", human_review_node)
    builder.add_node("retrieval_subgraph", retrieval_subgraph_node)
    builder.add_node("evidence_synthesis_node", evidence_synthesis_node)
    builder.add_node("method_design_node", method_design_node)
    builder.add_node("quality_gate_node", quality_gate_node)
    builder.add_node("report_node", report_node)
    builder.add_node("persist_node", persist_node)

    builder.add_edge(START, "intake_node")
    builder.add_edge("intake_node", "planning_node")
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
    builder.add_edge("retrieval_subgraph", "evidence_synthesis_node")
    builder.add_conditional_edges(
        "evidence_synthesis_node",
        _continue_unless_failed,
        {"continue": "method_design_node", "blocked": "report_node"},
    )
    builder.add_conditional_edges(
        "method_design_node",
        _continue_unless_failed,
        {"continue": "quality_gate_node", "blocked": "report_node"},
    )
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
