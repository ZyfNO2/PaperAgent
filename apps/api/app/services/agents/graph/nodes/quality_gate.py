"""Quality-gate middleware node for Re1.2 graph.

Emits the routing decision so the conditional edges in research_graph.py can
dispatch. The routing logic itself mirrors `_route_after_quality_gate` in
`research_graph.py`; keeping it here too so `quality_gate_node` is self-
documenting and traceable.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def quality_gate_node(state: ResearchState) -> dict[str, Any]:
    """Inspect evidence quality and emit `quality_gate_route`."""
    t0 = time.time()

    n_papers: int = len(state.get("verified_papers") or [])
    existing_verified = list(state.get("verified_papers") or [])
    # Re1.3 audit fix: if not enough accept papers, promote weak_papers
    # Cap: only promote baseline/parallel weak_papers, limit to top-10
    weak_papers = list(state.get("weak_papers") or [])
    _WEAK_PROMOTE_CAP = 10
    promoted = False
    if n_papers < 3 and weak_papers and not state.get("citation_expansion_done", False):
        # Only promote baseline/parallel (not survey/none)
        promotable = [p for p in weak_papers
                      if (p.get("relation_to_topic") or "none") in ("baseline", "parallel")]
        if not promotable:
            # Fallback: promote any weak_paper if no baseline/parallel
            promotable = weak_papers
        promoted_list = existing_verified + promotable[:_WEAK_PROMOTE_CAP]
        logger.info("quality_gate: promoting %d/%d weak_papers to verified_papers (had %d accept, cap=%d)",
                     min(len(promotable), _WEAK_PROMOTE_CAP), len(weak_papers), n_papers, _WEAK_PROMOTE_CAP)
        n_papers = len(promoted_list)
        promoted = True
    else:
        promoted_list = None

    quarantined: int = len(state.get("quarantined_candidates") or [])
    total: int = len(state.get("paper_candidates") or [1]) or 1
    baseline_n: int = len(state.get("baseline_candidates") or [])
    dataset_n: int = len(state.get("dataset_candidates") or [])
    repo_n: int = len(state.get("repo_candidates") or [])
    work_packages: int = len(state.get("work_packages") or [])
    repair_rounds: int = state.get("evidence_audit", {}).get("repair_rounds", 0)
    max_repair: int = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))

    # Re1.3: citation_expansion_done flag
    citation_done: bool = state.get("citation_expansion_done", False)

    if n_papers < 1 and repair_rounds < max_repair and not citation_done:
        route = "repair"
    elif not citation_done and n_papers >= 1:
        route = "citation_expander"
    else:
        route = "continue"

    summary = {
        "n_papers": n_papers,
        "n_weak": len(weak_papers),
        "n_quarantined": quarantined,
        "n_baseline": baseline_n,
        "n_dataset": dataset_n,
        "n_repo": repo_n,
        "n_work_packages": work_packages,
        "repair_rounds": repair_rounds,
        "weak_promoted": promoted,
    }
    trace = {
        "node": "quality_gate",
        "started_at": _now_iso(),
        "input_summary": summary,
        "output_summary": {"route": route},
        "tool_calls": ["quality_gate.rule_based"],
        "errors": [],
        "provider": "local",
        "ended_at": _now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
    }
    result = {
        "evidence_audit": {
            **state.get("evidence_audit", {}),
            "quality_gate_route": route,
            "quality_gate_snapshot": summary,
        },
        "trace_events": [trace],
    }
    if promoted and promoted_list is not None:
        result["verified_papers"] = promoted_list
        result["weak_papers"] = []
    return result
