"""LangGraph graph builder for Re2.

Wires 20 LangGraph nodes with conditional edges + targeted-repair loop +
citation expansion loop + devils_advocate revision loop.

Re2 changes:
  - conditional edge: feasibility_assessor → work_package / optimization_advisor
  - conditional edge: devils_advocate → human_gate / narrative_builder / optimization_advisor
  - narrative_revision_count to cap revision loops at MAX_NARRATIVE_REVISIONS
  - duplicate add_edge calls cleaned up
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

NODE_TIMEOUTS = {
    "topic_parser": 30,
    "verify": 45,
    "dataset_repo_extractor": 30,
    "feasibility_assessor": 20,
    "work_package": 30,
    "innovation_extractor": 30,
    "sota_matcher": 20,
    "narrative_builder": 45,
    "optimization_advisor": 20,
    "devils_advocate": 30,
}


def build_graph(*, checkpointer: Any | None = None) -> Any:
    """Build the compiled Re1.3 LangGraph pipeline."""
    graph = StateGraph(ResearchState)

    registry = graph_nodes.REGISTRY
    for name, fn in registry.items():
        graph.add_node(name, fn)

    # Linear spine (Re1.3: quality_filter inserted before verify)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "topic_parser")
    graph.add_edge("topic_parser", "search_planner")
    graph.add_edge("search_planner", "paper_retriever")
    graph.add_edge("paper_retriever", "quality_filter")     # Re1.3
    graph.add_edge("quality_filter", "verify")              # Re1.3
    graph.add_edge("verify", "quality_gate")

    # Conditional routing out of quality_gate (Re1.3: adds citation_expander)
    graph.add_conditional_edges(
        "quality_gate",
        _route_after_quality_gate,
        {
            "repair": "targeted_repair",
            "citation_expander": "citation_expander",   # Re1.3
            "continue": "dataset_repo_extractor",
            "blocked": "final_recommendation",
            "END": END,
        },
    )
    graph.add_edge("targeted_repair", "retrieve")            # loop back

    # Re1.3: citation_expander → verify (second round) → quality_gate (second round)
    graph.add_edge("citation_expander", "verify")
    # verify → quality_gate is already defined above (same edge, verify checks round internally)

    # Post-expansion linear spine (Re1.4: 6 analysis nodes inserted)
    graph.add_edge("dataset_repo_extractor", "evidence_graph_builder")
    graph.add_edge("evidence_graph_builder", "baseline_classifier")
    graph.add_edge("baseline_classifier", "feasibility_assessor")  # Re1.4
    # Re2: conditional edge — feasibility_assessor → work_package / optimization_advisor
    graph.add_conditional_edges(
        "feasibility_assessor",
        _route_after_feasibility,
        {
            "work_package": "work_package",
            "optimization_advisor": "optimization_advisor",
        },
    )
    graph.add_edge("work_package", "innovation_extractor")         # Re2: parallel fan-out
    graph.add_edge("work_package", "sota_matcher")                 # Re2: parallel fan-out
    graph.add_edge("innovation_extractor", "narrative_builder")    # Re2: fan-in
    graph.add_edge("sota_matcher", "narrative_builder")            # Re2: fan-in
    graph.add_edge("narrative_builder", "low_bar_review")
    graph.add_edge("low_bar_review", "optimization_advisor")        # Re1.4
    graph.add_edge("optimization_advisor", "devils_advocate")       # Re1.4
    # Re2: conditional edge — devils_advocate → human_gate / narrative_builder / optimization_advisor
    graph.add_conditional_edges(
        "devils_advocate",
        _route_after_devils,
        {
            "human_gate": "human_gate",
            "narrative_builder": "narrative_builder",
            "optimization_advisor": "optimization_advisor",
        },
    )
    graph.add_edge("human_gate", "final_recommendation")
    graph.add_edge("final_recommendation", END)

    # Conditional routing out of low_bar_review.
    graph.add_conditional_edges(
        "low_bar_review",
        _route_after_review,
        {
            "repair": "targeted_repair",
            "ready": "optimization_advisor",  # Re1.4: go to optimization, not human_gate
            "blocked": "final_recommendation",
        },
    )

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
    """Route after quality gate (Re1.3: adds citation_expander path).

    First round (citation_expansion_done=False):
      - n_papers < 1 and repair_rounds < max → repair
      - n_papers >= 1 → citation_expander (do expansion before continuing)
    
    Second round (citation_expansion_done=True):
      - n_papers < 1 → blocked (expansion didn't help, really stuck)
      - n_papers >= 1 → continue
    """
    n_papers = len(state.get("verified_papers") or [])
    repair_rounds = state.get("evidence_audit", {}).get("repair_rounds", 0)
    max_repair = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))
    citation_done = state.get("citation_expansion_done", False)

    if not citation_done:
        # First round
        if n_papers < 1 and repair_rounds < max_repair:
            return "repair"
        if n_papers < 1 and repair_rounds >= max_repair:
            return "blocked"
        # Have enough papers → do citation expansion first
        return "citation_expander"
    else:
        # Second round (after citation expansion)
        if n_papers < 1:
            return "blocked"  # expansion didn't help
        return "continue"


def _route_after_review(state: ResearchState) -> str:
    """Route after low-bar review.

    Honors low_bar_review.status:
      - "pass" → ready (evidence is sufficient)
      - "blocked" with repair_rounds >= max → blocked (give up gracefully)
      - otherwise → repair if rounds remain, else blocked
    """
    audit = state.get("evidence_audit", {})
    repair_rounds = audit.get("repair_rounds", 0)
    max_repair = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))

    # If low_bar_review passed, go to human_gate regardless of evidence count
    review = state.get("low_bar_review") or {}
    if review.get("status") == "pass":
        return "ready"

    if repair_rounds >= max_repair:
        return "blocked"

    total_evidence = (
        len(state.get("baseline_candidates") or [])
        + len(state.get("dataset_candidates") or [])
        + len(state.get("repo_candidates") or [])
        + len(state.get("work_packages") or [])
    )
    if total_evidence < 4:
        return "repair"
    return "ready"


def _route_after_feasibility(state: ResearchState) -> str:
    """Route after feasibility assessment (Re2).

    - not_recommended → optimization_advisor (skip work_package chain)
    - feasible / risky → work_package (normal flow)
    """
    verdict = state.get("feasibility_report", {}).get("verdict", "risky")
    if verdict == "not_recommended":
        return "optimization_advisor"
    return "work_package"


MAX_NARRATIVE_REVISIONS = 2


def _route_after_devils(state: ResearchState) -> str:
    """Route after devil's advocate review (Re2).

    - ACCEPT → human_gate
    - MINOR_REVISION → narrative_builder (if revisions < MAX)
    - MINOR_REVISION → human_gate (if revisions >= MAX, stop looping)
    - BLOCK → optimization_advisor (if revisions < MAX)
    - BLOCK → human_gate (if revisions >= MAX, stop looping)
    """
    verdict = state.get("review_report", {}).get("overall_verdict", "ACCEPT")
    revisions = state.get("narrative_revision_count", 0)

    if verdict == "ACCEPT":
        return "human_gate"

    if revisions >= MAX_NARRATIVE_REVISIONS:
        return "human_gate"

    if verdict == "MINOR_REVISION":
        return "narrative_builder"
    if verdict == "BLOCK":
        return "optimization_advisor"

    return "human_gate"


def default_graph() -> Any:
    if not hasattr(default_graph, "_instance") or default_graph._instance is None:
        default_graph._instance = build_graph()
    return default_graph._instance
