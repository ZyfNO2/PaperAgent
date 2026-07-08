"""devils_advocate — Re1.4 MVP node."""
import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)

def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    n_baselines = len(baselines)
    feas = state.get("feasibility_report") or {}
    feas_verdict = feas.get("verdict", "unknown")
    feas_score = feas.get("score", 0)

    if n_baselines >= 3 and feas_verdict == "feasible":
        verdict = "ACCEPT"
        score_val = 7
        reason = f"heuristic: {n_baselines} baselines, feasible"
    elif n_baselines >= 1 and feas_score >= 50:
        verdict = "MINOR_REVISION"
        score_val = 5
        reason = f"heuristic: {n_baselines} baselines, score={feas_score}"
    else:
        verdict = "BLOCK"
        score_val = 3
        reason = f"heuristic: {n_baselines} baselines, feas={feas_verdict}"

    scores = [{"dimension": f"D{i}", "score": score_val, "verdict": verdict,
               "reason": reason} for i in range(1, 6)]
    return {"dimension_scores": scores, "overall_verdict": verdict,
            "fabrication_alerts": [], "risks_identified": ["heuristic review"],
            "verdict_source": "heuristic"}

def devils_advocate_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    feasibility = state.get("feasibility_report") or {}
    innovations = state.get("innovation_points") or []
    # Re3.0 Fix 2.1: field name unified to research_narrative (singular)
    narrative = state.get("research_narrative") or {}
    work_packages = state.get("work_packages") or []

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import devils_advocate_graph as P
        built = P.build(topic, feasibility, innovations, narrative, work_packages)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("devils_advocate LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    block_count = state.get("devils_advocate_block_count", 0)
    if result.get("overall_verdict") == "BLOCK":
        block_count += 1

    trace = _emit("devils_advocate", t0,
                  {"n_innovation": len(innovations), "n_packages": len(work_packages)},
                  {"overall_verdict": result.get("overall_verdict", "unknown")},
                  [{"tool": "devils_advocate.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["review_report", "devils_advocate_block_count",
                              "trace_events"])
    return {"review_report": result,
            "devils_advocate_block_count": block_count,
            "trace_events": [trace]}
