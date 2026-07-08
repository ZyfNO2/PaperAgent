"""feasibility_assessor — Re1.4 MVP node."""
import time
import logging
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

from ._util import emit_trace as _emit

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
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []
    n_dataset = len(state.get("dataset_candidates") or [])
    n_repo = len(state.get("repo_candidates") or [])

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import feasibility_assessor as P
        built = P.build(topic, baselines, parallels, n_dataset, n_repo)
        # Re3.5: pass domain hint to prompt context
        domain = (state.get("topic_atoms") or {}).get("domain", "")
        user_with_domain = built["user"]
        if domain and domain != "unknown":
            user_with_domain += f"\n\n[领域提示] domain={domain}，请务必评估该领域的特定风险。"
        out = llm_router.call_json(user_with_domain, system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("feasibility_assessor LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    trace = _emit("feasibility_assessor", t0,
                  {"n_baseline": len(baselines), "n_dataset": n_dataset, "n_repo": n_repo},
                  {"verdict": result.get("verdict", "unknown"), "score": result.get("score", 0)},
                  [{"tool": "feasibility_assessor.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["feasibility_report", "trace_events"])
    return {"feasibility_report": result,
            "trace_events": [trace]}
