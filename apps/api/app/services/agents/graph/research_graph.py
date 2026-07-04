"""ResearchGraph — compose the 8 LangGraph nodes into a single pipeline.

The graph owns the full research pipeline (Intake → Parse → Retrieve → Verify →
Dataset/Repo → Evidence Audit → Work Package → Low-bar Review → Human Gate →
Final Recommendation), exposing a compiled graph with an in-memory checkpointer
so a case_id can be used as thread_id.

History:
  Re1.1: initial StateGraph(ResearchState) composition.
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
    """Build the compiled LangGraph pipeline for Re1.1."""
    graph = StateGraph(ResearchState)

    # Register nodes via the flat registry (name -> (state) -> patch).
    for name in (
        "retrieve",
        "verify",
        "dataset_repo",
        "evidence_auditor",
        "work_package",
        "low_bar_review",
        "human_gate",
        "final_recommendation",
    ):
        node_fn = graph_nodes.REGISTRY[name]
        graph.add_node(name, node_fn)

    # Linear pipeline. Future: add conditional edges around repair loops.
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "verify")
    graph.add_edge("verify", "dataset_repo")
    graph.add_edge("dataset_repo", "evidence_auditor")
    graph.add_edge("evidence_auditor", "work_package")
    graph.add_edge("work_package", "low_bar_review")
    graph.add_edge("low_bar_review", "human_gate")
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
                logger.exception("failed to init SqliteSaver; fall back to memory")
                checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


def default_graph() -> Any:
    """Build and memoize a single compiled graph for the API service."""
    if not hasattr(default_graph, "_instance") or default_graph._instance is None:
        default_graph._instance = build_graph()
    return default_graph._instance
