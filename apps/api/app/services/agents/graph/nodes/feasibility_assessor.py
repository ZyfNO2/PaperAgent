"""feasibility_assessor — Re1.4 MVP node."""
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
    nb = len(state.get("baseline_candidates") or [])
    nd = len(state.get("dataset_candidates") or [])
    nr = len(state.get("repo_candidates") or [])
    if nb >= 2 and nd >= 1:
        v, s = "feasible", 75
    elif nb >= 1:
        v, s = "risky", 50
    else:
        v, s = "not_recommended", 20
    return {"verdict": v, "score": s, "reason": f"heuristic: {nb}B/{nd}D/{nr}R",
            "100_plus_formula": {"baseline_weight": 100 if nb else 0,
                                  "module_weights": [1]*min(nr, 3),
                                  "estimated_total": (100 if nb else 0) + min(nr, 3)},
            "degradation_paths": []}

def feasibility_assessor_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    n_baseline = len(state.get("baseline_candidates") or [])
    n_parallel = len(state.get("parallel_candidates") or [])
    n_dataset = len(state.get("dataset_candidates") or [])
    n_repo = len(state.get("repo_candidates") or [])

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import feasibility_assessor as P
        built = P.build(topic, n_baseline, n_parallel, n_dataset, n_repo)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("feasibility_assessor LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    trace = _emit("feasibility_assessor", t0,
                  {"n_baseline": n_baseline, "n_dataset": n_dataset, "n_repo": n_repo},
                  {"verdict": result.get("verdict", "unknown"), "score": result.get("score", 0)},
                  [{"tool": "feasibility_assessor.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [])
    return {"feasibility_report": result,
            "trace_events": [trace]}
