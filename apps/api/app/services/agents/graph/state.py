"""ResearchState — shared state for the Re1.1 LangGraph research pipeline.

Every graph node receives this TypedDict and returns a partial patch (dict of
the fields it owns). Nodes MUST NOT mutate the state in place; they return
the fields they update and LangGraph merges them.

History:
  Re1.1: initial schema covering all 13 stages from SOP §4.
"""
from __future__ import annotations

from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    # --- Intake ---
    case_id: str
    topic: str
    user_constraints: dict[str, Any]

    # --- Topic parsing ---
    topic_atoms: dict[str, Any]

    # --- Search planning ---
    search_plan: dict[str, Any]

    # --- Retrieval ---
    raw_results: dict[str, list[dict[str, Any]]]

    # --- Paper verification ---
    paper_candidates: list[dict[str, Any]]
    verified_papers: list[dict[str, Any]]

    # --- Dataset / repo extraction (from verified papers first) ---
    dataset_candidates: list[dict[str, Any]]
    repo_candidates: list[dict[str, Any]]

    # --- Evidence audit + classification ---
    baseline_candidates: list[dict[str, Any]]
    parallel_candidates: list[dict[str, Any]]
    evidence_audit: dict[str, Any]

    # --- Work package + low-bar review ---
    work_packages: list[dict[str, Any]]
    low_bar_review: dict[str, Any]

    # --- Human gate (Re1.1: pass-through unless HUMAN_GATE_ENABLED=true) ---
    human_gate: dict[str, Any]

    # --- Final recommendation ---
    final_recommendation: dict[str, Any]

    # --- Telemetry ---
    trace_events: list[dict[str, Any]]
    provider_profile: str
    errors: list[dict[str, Any]]
