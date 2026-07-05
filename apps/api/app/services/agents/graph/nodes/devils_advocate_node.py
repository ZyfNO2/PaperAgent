"""devils_advocate — Re1.4 MVP node."""
import time, logging
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def _emit(node, t0, ins, out, tools, prov, errs):
    return {"node": node, "started_at": _now_iso(), "input_summary": ins,
            "output_summary": out, "tool_calls": tools, "errors": errs,
            "provider": prov, "ended_at": _now_iso(), "elapsed_s": round(time.time()-t0, 3)}

def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    has_baseline = len(baselines) >= 1
    if has_baseline:
        verdict = "ACCEPT"
        scores = [{"dimension": f"D{i}", "score": 6, "verdict": "PASS",
                   "reason": "heuristic: has baseline"} for i in range(1, 6)]
    else:
        verdict = "BLOCK"
        scores = [{"dimension": f"D{i}", "score": 3, "verdict": "BLOCK",
                   "reason": "heuristic: no baseline"} for i in range(1, 6)]
    return {"dimension_scores": scores, "overall_verdict": verdict,
            "fabrication_alerts": [], "risks_identified": ["heuristic review"],
            "verdict_source": "heuristic"}

def devils_advocate_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    feasibility = state.get("feasibility_report") or {}
    innovations = state.get("innovation_points") or []
    narrative = state.get("research_narratives") or {}
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

    trace = _emit("devils_advocate", t0,
                  {"n_innovation": len(innovations), "n_packages": len(work_packages)},
                  {"overall_verdict": result.get("overall_verdict", "unknown")},
                  [{"tool": "devils_advocate.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [])
    return {"review_report": result,
            "trace_events": [trace]}
