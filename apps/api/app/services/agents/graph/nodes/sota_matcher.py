"""sota_matcher — Re1.4 MVP node."""
import time
import logging
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

from ._util import emit_trace as _emit

def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    return {
        "comparison_papers": [{"title": b.get("title", ""), "year": b.get("year", "")}
                              for b in baselines[:3]],
        "metrics_to_compare": ["Accuracy", "F1", "mAP"],
        "ablation_suggestions": [
            {"name": "去掉模块B", "purpose": "验证模块B贡献", "expected_drop": "1-3%"},
            {"name": "去掉模块C", "purpose": "验证模块C贡献", "expected_drop": "1-3%"},
            {"name": "去掉B+C", "purpose": "验证整体创新", "expected_drop": "3-5%"}],
        "experiment_checklist": ["对比实验(≥3个baseline)", "消融实验(≥3组)",
                                  "参数敏感性实验(≥4组)", "定性分析(case study)"]
    }

def sota_matcher_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    baselines = state.get("baseline_candidates") or []

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import sota_matcher as P
        built = P.build(topic, baselines)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("sota_matcher LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    trace = _emit("sota_matcher", t0,
                  {"n_baseline": len(baselines)},
                  {"n_comparison": len(result.get("comparison_papers", []))},
                  [{"tool": "sota_matcher.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["sota_comparison", "trace_events"])
    return {"sota_comparison": result,
            "trace_events": [trace]}
