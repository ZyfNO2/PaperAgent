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


def merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """LangGraph reducer for dict state keys that may be written by multiple
    nodes in the same super-step (e.g. evidence_audit during fan-out / repair
    loops). Later writes win on key conflicts; both sides are merged otherwise.

    Re7.7: fixes ``InvalidUpdateError: At key 'evidence_audit': Can receive
    only one value per step`` observed intermittently on XD-09.
    """
    out: dict[str, Any] = dict(left or {})
    if right:
        out.update(right)
    return out


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
    evidence_audit: Annotated[dict[str, Any], merge_dict]

    # --- Work package + low-bar review ---
    work_packages: list[dict[str, Any]]
    low_bar_review: dict[str, Any]

    # --- Human gate (Re1.1: pass-through unless HUMAN_GATE_ENABLED=true) ---
    human_gate: dict[str, Any]
    human_gate_search: dict[str, Any]  # Re3.9.3: gate after search, before analysis

    # --- Final recommendation ---
    final_recommendation: dict[str, Any]
    # Re8.0 P1-3: Final Research Package — 7-section auditable object
    # (seed_audit_summary / tailor_summary / gate_results / ledger_entries /
    # evidence_gap_status / falsifiable_hypothesis / fused_verdict). Also
    # mirrored at final_recommendation["research_package"] for convenience.
    final_research_package: dict[str, Any]
    # Re8.0 P0-A: fused verdict surfaced at the state top level so that
    # diagnostic scripts and the Three-Tier PASS checker can read it
    # directly without diving into final_recommendation. Written by
    # final_recommendation_node alongside final_rec.fused_verdict.
    # Values: "GO" | "CONDITIONAL" | "RISKY" | "BLOCKED" | None (pre-pipeline)
    fused_verdict: str | None
    fused_verdict_rationale: str

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
    # Re8.0 post-audit: search results that cannot be attributed to any
    # evidence gap (gap_lookup miss + no plan_query_id). Tracked for
    # traceability only — does NOT mark any gap as partially_satisfied.
    # See spec.md "Evidence Gap Attribution Stability".
    unassigned_evidence: list[dict[str, Any]]

    # --- Telemetry ---
    trace_events: Annotated[list[dict[str, Any]], operator.add]
    provider_profile: str
    errors: Annotated[list[dict[str, Any]], operator.add]

    # === Re4.3 new fields ===
    narrative_revisions: list[dict[str, Any]]  # append-only revision history
    binding_validation: dict[str, Any]  # last validation result

    # === Re6.4 new fields ===
    novelty_review_verdict: str
    novelty_review_score: float
    pseudo_innovation_risks: list[str]
    pressure_points: list[dict[str, Any]]
    differentiation_matrix: list[dict[str, Any]]
    required_repairs: list[str]
    review_strengths: list[str]
    review_risks: list[str]
    novelty_review_error: str
    falsifiable_propositions: list[dict[str, Any]]
    novelty_evolution_log: list[dict[str, Any]]
    evidence_contexts: list[dict[str, Any]]  # Re7.6
    novelty_drafts: list[dict[str, Any]]  # Re7.6 D-09: P-M-I structured drafts
    claim_judgements: list[dict[str, Any]]  # Re7.6
    claim_judge_verdict: str  # Re7.6
    stop_reason: list[str]  # Re7.7: auditable STOP/RISKY/CONDITIONAL/PIVOT attribution

    # === Re8.0 new fields (Seeded Research) ===
    # Entry / run / network / reasoning policy (WP0 contract)
    entry_mode: str  # "topic_only" | "seeded_research"
    run_mode: str  # "full_agent" | "lite_chain" | "offline_replay"
    network_policy: str  # "online" | "cache_first" | "offline"
    reasoning_policy: str  # "react_reflection" | "chain_only"

    # Seed paper cards (post-verification). Re8.0 replaces the legacy
    # `user_papers` auto-accept path with audited SeedPaperCard objects.
    # Each card carries existence_status, role, and reproduction metadata.
    seed_cards: list[dict[str, Any]]
    # Candidate seeds prior to resolution (raw user input, never enters
    # verified_papers without passing SeedResolver).
    candidate_seeds: list[dict[str, Any]]

    # Method family cards (WP3) — 2-4 alternative method routes per topic
    method_families: list[dict[str, Any]]

    # Five Search Lanes (WP3 §7.3) — Anchor/Competing/Mechanism/Resource/
    # Counter-evidence. Each lane carries queries + gap_id reference.
    search_lanes: list[dict[str, Any]]

    # Evidence gaps (WP4) — every external search must bind to a gap_id
    evidence_gaps: list[dict[str, Any]]

    # Research reasoning ledger (WP6) — auditable structured decisions
    reasoning_ledger: Annotated[list[dict[str, Any]], operator.add]

    # Re8.0 WP5: Tailored method card produced by tailor_skill_adapter.
    # Only populated for entry_mode == "seeded_research"; absent for topic_only.
    tailored_method: dict[str, Any]

    # Re8.0 WP5: Novelty Review P-M-I enhancement fields (additive).
    # All default to empty/"unspecified" when LLM omits them; see
    # normalize_review_output in novelty_review.py for the schema chokepoint.
    problem_method_insight: dict[str, Any]
    contributions: dict[str, Any]
    falsifiable_hypothesis: str
    minimum_key_experiment: str
    contribution_type: str
    review_generated_by: str

    # Re8.0 WP6: Reflection Gate evaluation results keyed by gate_name.
    # Re8.2 separates evaluation entries from reuse events.  Historical
    # results remain append-only across cycles, while ``gate_cycle_start_index``
    # defines which suffix belongs to the active bounded evaluation cycle.
    reflection_gate_results: dict[str, list[dict[str, Any]]]

# Re8.2 WP1: last verified pass per gate.  A pass may be reused only when
    # its stable dependency fingerprint matches the current input.
    last_gate_pass: Annotated[dict[str, dict[str, Any]], merge_dict]
    # Active evaluation cycle and its first index in reflection_gate_results.
    gate_cycle_id: Annotated[dict[str, int], merge_dict]
    gate_cycle_start_index: Annotated[dict[str, int], merge_dict]
    gate_input_fingerprint: Annotated[dict[str, str], merge_dict]
    # Reuse is auditable but never contributes to evaluation round count.
    gate_reuse_count: Annotated[dict[str, int], merge_dict]
    gate_evaluation_events: Annotated[list[dict[str, Any]], operator.add]
    gate_reuse_events: Annotated[list[dict[str, Any]], operator.add]

    # Re8.0 WP6: ReAct action log — append-only audit trail of every
    # tool call attempted by the Full Agent ReAct loop. Each entry:
    #   {gap_id, tool, query, expected_success, actual_result, next_action}
    # Lite Chain / Offline Replay leave this empty (no ReAct invocations).
    react_actions: Annotated[list[dict[str, Any]], operator.add]

    # Budget / search caps (WP0 contract)
    search_budget: dict[str, Any]
