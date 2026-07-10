"""ResearchState — shared state for the Re1.1 LangGraph research pipeline.

Every graph node receives this TypedDict and returns a partial patch (dict of
the fields it owns). Nodes MUST NOT mutate the state in place; they return
the fields they update and LangGraph merges them.

History:
  Re1.1: initial schema covering all 13 stages from SOP §4.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ResearchState(TypedDict, total=False):
    # --- Intake ---
    case_id: str
    topic: str
    user_constraints: dict[str, Any]
    user_papers: list[dict[str, Any]]  # Re3.1: papers uploaded by user before run

    # --- Topic parsing ---
    topic_atoms: dict[str, Any]

    # --- Search planning ---
    search_plan: dict[str, Any]

    # --- Retrieval ---
    raw_results: dict[str, list[dict[str, Any]]]

    # --- Evidence graph (Re1.2: front-end contract, SOP §5.8) ---
    evidence_graph: dict[str, Any]

    # --- Paper verification ---
    paper_candidates: list[dict[str, Any]]
    verified_papers: list[dict[str, Any]]
    weak_papers: list[dict[str, Any]]  # Re1.3 audit fix: weak_reject separated from verified

    # --- Dataset / repo extraction (from verified papers first) ---
    dataset_candidates: list[dict[str, Any]]
    repo_candidates: list[dict[str, Any]]

    # --- Evidence audit + classification ---
    baseline_candidates: list[dict[str, Any]]
    parallel_candidates: list[dict[str, Any]]
    dataset_papers: list[dict[str, Any]]
    surveys: list[dict[str, Any]]
    evidence_audit: dict[str, Any]

    # --- Work package + low-bar review ---
    work_packages: list[dict[str, Any]]
    low_bar_review: dict[str, Any]

    # --- Human gate (Re1.1: pass-through unless HUMAN_GATE_ENABLED=true) ---
    human_gate: dict[str, Any]
    human_gate_search: dict[str, Any]  # Re3.9.3: gate after search, before analysis

    # --- Final recommendation ---
    final_recommendation: dict[str, Any]

    # === Re1.3 new fields ===
    # Quality filter results
    filter_results: dict[str, Any]

    # Seed papers (auto-selected by citation_expander)
    seed_papers: list[dict[str, Any]]

    # Expanded papers from citation expansion (pre-verify)
    expanded_papers: list[dict[str, Any]]

    # Surveys found during citation expansion
    surveys_found: list[dict[str, Any]]

    # Repos found during citation expansion
    repos_found: list[dict[str, Any]]

    # Citation expansion done flag (prevents infinite loop)
    citation_expansion_done: bool

    # Re6.1: explicit verify scope to disambiguate verify_node call paths
    #   "search"   → quality_filter → verify (first round / repair loop)
    #   "expanded" → citation_expander → verify (second round)
    #   "repair"   → targeted_repair repair-loop verify
    verify_scope: str

    # Re6.1: targeted_repair outcome for conditional routing
    #   "queries_ready"  → n_queries > 0, proceed to paper_retriever
    #   "no_query"       → n_queries == 0, route to quality_gate or final
    #   "exhausted"      → repair round cap reached
    repair_outcome: str
    repair_no_query_reason: str
    repair_query_ids: list[str]

    # === Re1.4 new fields ===
    feasibility_report: dict[str, Any]
    innovation_points: list[dict[str, Any]]
    stitching_plan: dict[str, Any]
    sota_comparison: dict[str, Any]
    research_narrative: dict[str, Any]
    optimization_directions: dict[str, Any]
    review_report: dict[str, Any]

    # === Re2 new fields ===
    narrative_revision_count: int  # devils_advocate回环计数器
    devils_advocate_block_count: int  # BLOCK verdict retry counter (Re3.3)

    # === Re3.0 new fields ===
    search_steps: list[dict[str, Any]]  # React search agent step log

    # --- Telemetry ---
    trace_events: Annotated[list[dict[str, Any]], operator.add]
    provider_profile: str
    errors: Annotated[list[dict[str, Any]], operator.add]

    # === Re4.3 new fields ===
    narrative_revisions: list[dict[str, Any]]  # append-only revision history
    binding_validation: dict[str, Any]  # last validation result
