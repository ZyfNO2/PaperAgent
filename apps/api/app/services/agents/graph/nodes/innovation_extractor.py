"""innovation_extractor — Re1.4 MVP node."""
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
    parallels = state.get("parallel_candidates") or []
    b_title = (baselines[0].get("title", "") if baselines else "未知baseline")
    p_title = (parallels[0].get("title", "") if parallels else "未知parallel")
    return {
        "innovation_points": [{"description": f"在{b_title}基础上借鉴{p_title}的模块",
                                "baseline_used": b_title, "stitched_modules": [p_title],
                                "stitching_plan": "待LLM生成", "estimated_difficulty": "中"}],
        "stitching_plan": {"baseline_model": b_title, "module_b": p_title, "module_c": "",
                           "stitching_steps": ["1. 复现baseline", "2. 提取parallel模块", "3. 拼接测试"],
                           "risk_notes": ["heuristic fallback，需人工确认"]}
    }

def innovation_extractor_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import innovation_extractor as P
        built = P.build(topic, baselines, parallels)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        if isinstance(out, dict):
            result_inn = out.get("innovation_points", [])
            result_plan = out.get("stitching_plan", {})
        else:
            h = _heuristic(state)
            result_inn, result_plan = h["innovation_points"], h["stitching_plan"]
        prov = "fast_json"
    except Exception as exc:
        logger.warning("innovation_extractor LLM failed: %s — heuristic fallback", exc)
        h = _heuristic(state)
        result_inn, result_plan = h["innovation_points"], h["stitching_plan"]
        prov = "heuristic"

    trace = _emit("innovation_extractor", t0,
                  {"n_baseline": len(baselines), "n_parallel": len(parallels)},
                  {"n_innovation": len(result_inn)},
                  [{"tool": "innovation_extractor.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [])
    return {"innovation_points": result_inn, "stitching_plan": result_plan,
            "trace_events": [trace]}
