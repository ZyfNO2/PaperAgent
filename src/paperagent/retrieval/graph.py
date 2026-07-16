from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from paperagent.retrieval.gate import retrieval_gate
from paperagent.retrieval.prepare_search import prepare_search_node
from paperagent.retrieval.search_tool import search_tool_node
from paperagent.retrieval.verify_evidence import verify_evidence_node
from paperagent.state import PaperAgentState


def build_retrieval_graph() -> Any:
    builder = StateGraph(PaperAgentState)
    builder.add_node("prepare_search_node", prepare_search_node)
    builder.add_node("search_tool_node", search_tool_node)
    builder.add_node("verify_evidence_node", verify_evidence_node)
    builder.add_edge(START, "prepare_search_node")
    builder.add_edge("prepare_search_node", "search_tool_node")
    builder.add_edge("search_tool_node", "verify_evidence_node")
    builder.add_conditional_edges(
        "verify_evidence_node",
        retrieval_gate,
        {
            "enough": END,
            "retry_under_budget": "prepare_search_node",
            "budget_exhausted": END,
        },
    )
    return builder.compile()
