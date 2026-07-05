"""LangGraph graph builder for Re1.2.

Wires 14 LangGraph nodes with conditional edges + targeted-repair loop.

History:
  Re1.2: extracted repair/quality-gate routing out of the linear chain.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from apps.api.app.services.agents.graph import nodes as graph_nodes
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def build_graph(*, checkpointer: Any | None = None) -> Any:
    """Build the compiled Re1.2 LangGraph pipeline."""
    graph = StateGraph(ResearchState)

    registry = graph_nodes.REGISTRY
    for name, fn in registry.items():
        graph.add_node(name, fn)

    # Linear spine (intake → retriever uses Re1.1 node key names so legacy
    # reports/tests that assert trace-fire events by those names still pass).
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "topic_parser")
    graph.add_edge("topic_parser", "search_planner")
    graph.add_edge("search_planner", "paper_retriever")
    graph.add_edge("paper_retriever", "verify")
    graph.add_edge("verify", "quality_gate")

    # Conditional routing out of quality_gate (SOP §4 / §7).
    graph.add_conditional_edges(
        "quality_gate",
        _route_after_quality_gate,
        {
            "repair": "targeted_repair",
            "continue": "dataset_repo",
            "blocked": "final_recommendation",
            "END": END,
        },
    )
    graph.add_edge("targeted_repair", "retrieve")            # loop back
    graph.add_edge("dataset_repo", "evidence_graph_builder")
    graph.add_edge("evidence_graph_builder", "evidence_auditor")
    graph.add_edge("evidence_auditor", "work_package")
    graph.add_edge("work_package", "low_bar_review")

    # Conditional routing out of low_bar_review.
    graph.add_conditional_edges(
        "low_bar_review",
        _route_after_review,
        {
            "repair": "targeted_repair",
            "ready": "human_gate",
            "blocked": "final_recommendation",
        },
    )
    # human_gate in Re1.2 still passthrough unless interrupt enabled.
    graph.add_edge("human_gate", "final_recommendation")
    graph.add_edge("final_recommendation", END)

    if checkpointer is None:
        if os.environ.get("LANGGRAPH_CHECKPOINTER", "memory").lower() == "memory":
            checkpointer = MemorySaver()
        else:
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
                import sqlite3
                db_path = os.environ.get("LANGGRAPH_CHECKPOINT_DB",
                                         "data/research_graph.db")
                os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
                conn = sqlite3.connect(db_path)
                checkpointer = SqliteSaver(conn)
            except Exception:
                logger.exception("failed to init SqliteSaver; fallback to memory")
                checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


def _route_after_quality_gate(state: ResearchState) -> str:
    """Route after quality gate.

    Downstream gaps (baseline / dataset / repo / work package) are evaluated
    later in the spine, so this gate only inspects the IMMEDIATE upstream
    product: verified papers + quarantine.  The spine then drives additional
    targeted_repair visits via the low-bar-review branch if downstream gaps
    remain.
    """
    n_papers = len(state.get("verified_papers") or [])
    quarantined = len(state.get("quarantined_candidates") or [])
    total = len(state.get("paper_candidates") or [1]) or 1
    repair_rounds = state.get("evidence_audit", {}).get("repair_rounds", 0)
    max_repair = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))

    if n_papers < 1 and repair_rounds < max_repair:
        return "repair"
    if quarantined / max(total, 1) > 0.4 and repair_rounds < max_repair:
        return "repair"
    return "continue"


def _route_after_review(state: ResearchState) -> str:
    """Route after low-bar review (SOP §5.10).

    Routes:
      - downstream gap + cap not exhausted -> repair -> back to retrieve
      - downstream gap + cap exhausted      -> final (with explicit repair_plan)
      - no gap                             -> final
    """
    audit = state.get("evidence_audit", {})
    repair_rounds = audit.get("repair_rounds", 0)
    max_repair = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))
    if repair_rounds >= max_repair:
        # Repair attempts exhausted; expose repair_plan in final.
        return "blocked"
    # Any downstream gap -> repair.
    if (len(state.get("baseline_candidates") or [])
            + len(state.get("dataset_candidates") or [])
            + len(state.get("repo_candidates") or [])
            + len(state.get("work_packages") or [])) < 4:
        return "repair"
    return "ready"


def default_graph() -> Any:
    if not hasattr(default_graph, "_instance") or default_graph._instance is None:
        default_graph._instance = build_graph()
    return default_graph._instance
