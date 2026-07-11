"""StageContract v1 — per-node I/O declaration for the LangGraph pipeline.

Inspired by AutoResearchClaw's researchclaw/pipeline/contracts.py (MIT),
rewritten as Pydantic v2 model for PaperAgent's LangGraph nodes.

Each contract declares:
  - node_name: LangGraph node identifier
  - reads: state keys this node reads (must exist before execution)
  - writes: state keys this node produces
  - optional_reads: state keys that enhance output but aren't required
  - fallback_source: which heuristic/function provides degraded output
  - error_code: unique error identifier for diagnostics
  - version: contract version for future migration tracking
  - dod: Definition of Done — human-readable
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StageContract(BaseModel):
    """Per-node I/O contract."""
    node_name: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    optional_reads: tuple[str, ...] = ()
    fallback_source: str | None = None
    error_code: str
    version: str = "1.0"
    dod: str = ""

    def validate_state(self, state: dict[str, Any]) -> list[str]:
        """Check that all required reads are present in state.

        Returns list of missing keys (empty = all present).
        """
        return [k for k in self.reads if k not in state or state[k] is None]


# Registry — one per graph node
CONTRACTS: dict[str, StageContract] = {
    "intake": StageContract(
        node_name="intake",
        reads=(),
        writes=("topic", "target_tier", "topic_atoms", "constraints"),
        error_code="E40_INTAKE_FAIL",
        dod="Topic received and stored in state",
    ),
    "topic_parser": StageContract(
        node_name="topic_parser",
        reads=("topic",),
        writes=("topic_atoms",),
        fallback_source="_heuristic_parse",
        error_code="E40_TOPIC_PARSE_FAIL",
        dod="method/task/object keywords extracted and English-verified",
    ),
    "search_planner": StageContract(
        node_name="search_planner",
        reads=("topic", "topic_atoms"),
        writes=("search_queries",),
        fallback_source="_default_queries",
        error_code="E40_SEARCH_PLAN_FAIL",
        dod=">=2 search queries generated for each source category",
    ),
    "search_agent": StageContract(
        node_name="search_agent",
        reads=("topic", "topic_atoms", "search_queries"),
        writes=("raw_papers", "repo_candidates", "source_ledger"),
        optional_reads=("user_papers",),
        fallback_source="heuristic_candidates",
        error_code="E40_SEARCH_FAIL",
        dod=">=1 paper or repo collected from enabled sources",
    ),
    "quality_filter": StageContract(
        node_name="quality_filter",
        reads=("raw_papers", "topic_atoms"),
        writes=("filtered_papers",),
        error_code="E40_FILTER_FAIL",
        dod="Non-relevant papers filtered out; remaining >= 0",
    ),
    "verify": StageContract(
        node_name="verify",
        reads=("filtered_papers", "topic_atoms"),
        writes=("verified_papers", "verification_results"),
        fallback_source="heuristic_verify",
        error_code="E40_VERIFY_FAIL",
        dod="Each paper has accept/weak_reject/reject verdict",
    ),
    "citation_expander": StageContract(
        node_name="citation_expander",
        reads=("verified_papers", "topic_atoms"),
        writes=("expanded_papers",),
        optional_reads=("source_policy",),
        fallback_source="skip_expansion",
        error_code="E40_CITATION_EXPAND_FAIL",
        dod="Citation expansion attempted for enabled sources only",
    ),
    "innovation_extractor": StageContract(
        node_name="innovation_extractor",
        reads=("topic", "topic_atoms", "baseline_candidates", "parallel_candidates"),
        writes=("innovation_points", "stitching_plan", "dataset_candidates", "trace_events"),
        fallback_source="_heuristic",
        error_code="E43_INNOVATION_FAIL",
        dod="Each innovation_point has >=1 candidate_id or marked needs_evidence",
        version="1.1",
    ),
    "narrative_builder": StageContract(
        node_name="narrative_builder",
        reads=("topic", "innovation_points", "feasibility_report"),
        writes=("research_narrative", "narrative_revisions", "narrative_revision_count", "trace_events"),
        fallback_source="_heuristic",
        error_code="E43_NARRATIVE_FAIL",
        dod="Narrative revision appended to history with revision_id and parent_revision_id",
        version="1.1",
    ),
    "work_package": StageContract(
        node_name="work_package",
        reads=("topic", "topic_atoms", "baseline_candidates", "parallel_candidates",
               "dataset_candidates", "repo_candidates", "user_constraints"),
        writes=("work_packages", "evidence_audit", "trace_events", "errors"),
        fallback_source="evidence_gap_repair",
        error_code="E43_WORK_PACKAGE_FAIL",
        dod="Each work_package has objective+method+deliverable or marked evidence_gap",
        version="1.1",
    ),
}


def get_contract(node_name: str) -> StageContract | None:
    return CONTRACTS.get(node_name)
