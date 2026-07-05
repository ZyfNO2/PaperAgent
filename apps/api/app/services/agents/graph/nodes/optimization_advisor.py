"""optimization_advisor — Re1.4 MVP node."""
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
    feas = state.get("feasibility_report", {})
    verdict = feas.get("verdict", "risky")
    if verdict == "feasible":
        paths = [{"direction": "增加数据增强策略", "expected_gain": "提升2-5%",
                  "difficulty": "低", "action_items": ["调研CutMix/Mosaic效果"]}]
        degradation = [{"path": "去掉一个创新模块，仅保留核心改进",
                         "trade_off": "创新点减少但可毕业", "survival_rate": "高"}]
    else:
        paths = [{"direction": "简化题目范围", "expected_gain": "降低复现难度",
                  "difficulty": "低", "action_items": ["收缩到单一数据集/单一场景"]}]
        degradation = [{"path": "换用更简单的baseline", "trade_off": "创新性降低",
                         "survival_rate": "高"},
                       {"path": "改投更低级别期刊", "trade_off": "Q4→无级别",
                         "survival_rate": "极高"}]
    return {"optimization_paths": paths, "degradation_paths": degradation,
            "risk_mitigation": ["优先复现baseline确认代码可运行", "准备备选数据集"]}

def optimization_advisor_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    feasibility = state.get("feasibility_report") or {}
    innovations = state.get("innovation_points") or []
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import optimization_advisor as P
        built = P.build(topic, feasibility, innovations, baselines, parallels)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("optimization_advisor LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    trace = _emit("optimization_advisor", t0,
                  {"feasibility": feasibility.get("verdict", "unknown")},
                  {"n_paths": len(result.get("optimization_paths", []))},
                  [{"tool": "optimization_advisor.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [])
    current_count = state.get("narrative_revision_count", 0)
    return {"optimization_directions": result,
            "narrative_revision_count": current_count + 1,
            "trace_events": [trace]}
