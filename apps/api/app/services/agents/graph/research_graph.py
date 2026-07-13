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
from apps.api.app.services.agents.graph.nodes.reflection_gates import route_after_gate
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
    # Re8.0: seed_resolver audits user-uploaded candidate_seeds before any
    # promotion to verified_papers. No-op when entry_mode == "topic_only"
    # or candidate_seeds is empty, so topic_only callers see no change.
    graph.add_edge("intake", "seed_resolver")
    # Re8.0 WP6: seed_audit_gate reviews seed cards (real? role-correct?
    # info-sufficient?) before any downstream consumption. Short-circuits
    # to "pass" for topic_only / non-react-reflection modes (no-op).
    graph.add_edge("seed_resolver", "seed_audit_gate")
    # Re8.0 P1-1: fulltext_acquisition runs BEFORE paper_understanding so
    # that DOI/arXiv seeds get their PDFs downloaded first. paper_understanding
    # then parses all PDFs (user-uploaded + newly downloaded) in a single
    # pass. No-op for topic_only / offline / no verified metadata_only cards.
    #
    # Re8.0 P0-2: conditional repair routing — when seed_audit_gate emits
    # verdict=revise and round_idx < REFLECTION_GATE_MAX_ROUNDS, route
    # back to seed_resolver (re-resolve seeds with repair hints).
    # verdict=pass / unresolved / cap-reached → forward to
    # fulltext_acquisition. Lite Chain / Offline Replay always emit pass
    # (generated_by=skip), so they route forward — no behavior change.
    graph.add_conditional_edges(
        "seed_audit_gate",
        lambda state: route_after_gate(state, "seed_audit_gate"),
        {
            "fulltext_acquisition": "fulltext_acquisition",  # forward
            "seed_resolver": "seed_resolver",              # repair
        },
    )
    # Re8.0 post-audit: fulltext_acquisition → paper_understanding (was
    # reversed). For DOI/arXiv seeds, seed_resolver only fetches metadata;
    # fulltext_acquisition downloads the PDF; paper_understanding then
    # parses it to extract method/task/dataset/environment fields. The
    # previous order (paper_understanding first) meant the first pass had
    # no PDF to parse, and the downloaded PDF was never re-parsed.
    graph.add_edge("fulltext_acquisition", "paper_understanding")
    # Re8.0 WP2: paper_understanding parses seed PDFs and fills understanding
    # fields (method_summary, dataset_and_metrics, ...) on SeedPaperCards.
    # No-op when no seed card has a PDF, so topic_only callers see no change.
    graph.add_edge("paper_understanding", "method_family_explorer")
    graph.add_edge("method_family_explorer", "topic_parser")
    graph.add_edge("topic_parser", "search_planner")
    graph.add_edge("search_planner", "paper_retriever")
    # Conditional: skip filter+verify when 0 papers (go straight to quality_gate)
    graph.add_conditional_edges(
        "paper_retriever",
        _route_after_search,
        {
            "filter": "quality_filter",
            "skip": "quality_gate",
        },
    )
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
    # Re3.0: repair loop goes back to paper_retriever (now search_agent)
    # Re6.1 Fix A: conditional edge — route based on repair_outcome
    graph.add_conditional_edges(
        "targeted_repair",
        _route_after_targeted_repair,
        {
            "paper_retriever": "paper_retriever",   # queries_ready → search
            "quality_gate": "quality_gate",          # no_query / exhausted → gate decides
            "final_recommendation": "final_recommendation",  # exhausted + no evidence
        },
    )

    # Re1.3: citation_expander → verify (second round) → quality_gate (second round)
    # Re6.1 Fix B: conditional edge — skip verify when n_expanded == 0
    graph.add_conditional_edges(
        "citation_expander",
        _route_after_citation_expander,
        {
            "verify": "verify",
            "skip": "quality_gate",
        },
    )
    # verify → quality_gate is already defined above (same edge, verify checks round internally)

    # Post-expansion linear spine (Re1.4: 6 analysis nodes inserted)
    graph.add_edge("dataset_repo_extractor", "evidence_graph_builder")
    graph.add_edge("evidence_graph_builder", "baseline_classifier")
    graph.add_edge("baseline_classifier", "feasibility_assessor")  # Re1.4
    # Re3.9.3: Insert human_gate_search between feasibility_assessor and work_package
    graph.add_conditional_edges(
        "feasibility_assessor",
        _route_after_feasibility,
        {
            "work_package": "human_gate_search",       # Re3.9.3: gate before analysis
            "optimization_advisor": "optimization_advisor",  # risky/not_recommended skips gate
        },
    )
    graph.add_edge("human_gate_search", "work_package")  # Re3.9.3: gate → work_package
    # Re7.6: compile evidence before generating innovations
    graph.add_edge("work_package", "evidence_context")
    # Re8.0 WP5+WP6: tailor_skill_adapter produces tailored_method from
    # evidence_context + method_families; tailor_gate reviews it (module
    # compatibility / simpler route / falsifiability). Both are no-ops
    # for topic_only (activation gate on entry_mode == "seeded_research").
    graph.add_edge("evidence_context", "tailor_skill_adapter")
    graph.add_edge("tailor_skill_adapter", "tailor_gate")
    # Re8.0 P0-2: conditional repair routing — when tailor_gate emits
    # verdict=revise and round_idx < REFLECTION_GATE_MAX_ROUNDS, route
    # back to search_planner (targeted re-search based on
    # re_search_requests). verdict=pass / unresolved / cap-reached →
    # forward to innovation_extractor.
    graph.add_conditional_edges(
        "tailor_gate",
        lambda state: route_after_gate(state, "tailor_gate"),
        {
            "innovation_extractor": "innovation_extractor",  # forward
            "search_planner": "search_planner",              # repair
        },
    )
    graph.add_edge("work_package", "sota_matcher")                 # Re2: parallel fan-out
    # Re6.4: Insert novelty review + falsifiability between innovation and narrative
    graph.add_edge("innovation_extractor", "novelty_draft")
    graph.add_edge("novelty_draft", "novelty_review")
    # Re8.0 WP6: final_review_gate reviews novelty verdict + falsifiable
    # hypothesis + pressure points (narrative vs evidence / similar work /
    # need extra evidence). Short-circuits for non-react-reflection modes.
    graph.add_edge("novelty_review", "final_review_gate")
    # Re8.0 P0-2: conditional repair routing — when final_review_gate
    # emits verdict=revise and round_idx < REFLECTION_GATE_MAX_ROUNDS,
    # route back to evidence_context (compile more evidence).
    # verdict=pass / unresolved / cap-reached → forward to falsifiability.
    graph.add_conditional_edges(
        "final_review_gate",
        lambda state: route_after_gate(state, "final_review_gate"),
        {
            "falsifiability": "falsifiability",  # forward
            "evidence_context": "evidence_context",  # repair
        },
    )
    graph.add_edge("falsifiability", "claim_judge")                # Re7.6: judge claims
    graph.add_edge("claim_judge", "narrative_builder")             # Re7.6 fan-in
    graph.add_edge("sota_matcher", "narrative_builder")            # Re2: fan-in
    graph.add_edge("narrative_builder", "low_bar_review")
    # low_bar_review uses conditional edge (below), no static edge
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


def _route_after_search(state: ResearchState) -> str:
    """Route after paper_retriever: skip filter+verify if 0 papers found."""
    n_candidates = len(state.get("paper_candidates") or [])
    if n_candidates == 0:
        return "skip"
    return "filter"


def _route_after_quality_gate(state: ResearchState) -> str:
    """Route after quality gate (Re1.3: adds citation_expander path).

    Re2.3 Fix 5: 0 accept + ≥3 total candidates → repair (not promote weak)
    Re2.4: sufficiency gate — n_papers < 3 + repair_rounds < max → repair

    First round (citation_expansion_done=False):
      - 0 accept + ≥3 total → repair (Fix 5)
      - n_papers < 1 and repair_rounds < max → repair
      - n_papers < 1 and repair_rounds >= max → blocked
      - n_papers < 3 and repair_rounds < max → repair (sufficiency gate)
      - n_papers >= 1 → citation_expander (do expansion before continuing)
    
    Second round (citation_expansion_done=True):
      - n_papers < 1 → blocked (expansion didn't help, really stuck)
      - n_papers >= 1 → continue
    """
    n_papers = len(state.get("verified_papers") or [])
    weak_n = len(state.get("weak_papers") or [])
    n_total = n_papers + weak_n
    repair_rounds = state.get("evidence_audit", {}).get("repair_rounds", 0)
    max_repair = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))
    citation_done = state.get("citation_expansion_done", False)

    if not citation_done:
        # First round
        # Fix 5 (Re2.3): 0 accept + has candidates → repair
        if n_papers == 0 and n_total >= 3 and repair_rounds < max_repair:
            return "repair"
        if n_papers < 1 and repair_rounds < max_repair:
            return "repair"
        if n_papers < 1 and repair_rounds >= max_repair:
            return "blocked"
        # Re2.4: sufficiency gate — not enough papers → repair
        if n_papers < 3 and repair_rounds < max_repair:
            return "repair"
        # Have enough papers → do citation expansion first
        return "citation_expander"
    else:
        # Second round (after citation expansion)
        if n_papers < 1:
            return "blocked"  # expansion didn't help
        return "continue"


def _route_after_citation_expander(state: ResearchState) -> str:
    """Route after citation_expander: skip verify when no papers were expanded.

    Re6.1 Fix B: when n_expanded == 0, verify_node would fall back to
    paper_candidates and re-verify already-accepted papers (wiping them out
    if the LLM returns empty).  Route to quality_gate instead and set
    verify_scope so any downstream consumer learns the expansion was empty.
    """
    expanded = list(state.get("expanded_papers") or [])
    if len(expanded) > 0:
        return "verify"
    return "skip"


def _route_after_targeted_repair(state: ResearchState) -> str:
    """Route after targeted_repair based on repair_outcome (Re6.1 Fix A).

    Reads ``repair_outcome`` from state and routes:

    - ``queries_ready`` (n_queries > 0)  → paper_retriever (normal repair)
    - ``no_query`` (n_queries == 0)      → quality_gate (let gate decide:
                                            weak promote vs. blocked)
    - ``exhausted`` (round cap reached)  → quality_gate or final
                                            recommendation if no evidence
    """
    outcome = state.get("repair_outcome", "")
    n_papers = len(state.get("verified_papers") or [])
    n_weak = len(state.get("weak_papers") or [])
    n_baseline = len(state.get("baseline_candidates") or [])
    has_evidence = (n_papers + n_weak) > 0 or n_baseline > 0

    if outcome == "queries_ready":
        return "paper_retriever"

    if outcome == "exhausted":
        # Round cap: if we already have evidence, let gate handle it;
        # otherwise send to final recommendation.
        if has_evidence:
            return "quality_gate"
        return "final_recommendation"

    # outcome == "no_query" (or any unexpected value)
    # No new search intent — let quality_gate decide whether to promote
    # weak papers or mark the case as blocked.
    return "quality_gate"


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
MAX_BLOCK_RETRIES = 1  # Re3.3: BLOCK 最多重试 1 次（共 2 次 BLOCK 判断）


def _route_after_devils(state: ResearchState) -> str:
    """Route after devil's advocate review (Re2/Re3.3).

    - ACCEPT → human_gate
    - MINOR_REVISION → narrative_builder (if revisions < MAX)
    - MINOR_REVISION → human_gate (if revisions >= MAX, stop looping)
    - BLOCK → optimization_advisor (if block_count < MAX_BLOCK_RETRIES AND feasibility allows)
    - BLOCK → human_gate (if block_count >= MAX_BLOCK_RETRIES OR feasibility=not_recommended)
    """
    verdict = state.get("review_report", {}).get("overall_verdict", "ACCEPT")
    revisions = state.get("narrative_revision_count", 0)
    block_count = state.get("devils_advocate_block_count", 0)
    feas_verdict = state.get("feasibility_report", {}).get("verdict", "")

    if verdict == "ACCEPT":
        return "human_gate"

    if revisions >= MAX_NARRATIVE_REVISIONS:
        return "human_gate"

    # If feasibility is not_recommended, there's no evidence to optimize — stop looping
    if feas_verdict == "not_recommended" and verdict == "BLOCK":
        return "human_gate"

    if verdict == "MINOR_REVISION":
        return "narrative_builder"
    if verdict == "BLOCK":
        # Re3.3: use independent block counter to prevent infinite loop
        if block_count <= MAX_BLOCK_RETRIES:
            return "optimization_advisor"
        return "human_gate"

    return "human_gate"


def default_graph() -> Any:
    if not hasattr(default_graph, "_instance") or default_graph._instance is None:
        default_graph._instance = build_graph()
    return default_graph._instance
