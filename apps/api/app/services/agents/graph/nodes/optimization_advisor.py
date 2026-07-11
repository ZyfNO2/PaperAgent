"""optimization_advisor — Re1.4 MVP node.

Re7.6: optional unified_router path via OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER=1.
"""
import os
import time
import logging
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState


def _use_unified() -> bool:
    return os.environ.get("OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER", "1") == "1"

logger = logging.getLogger(__name__)

from ._util import emit_trace as _emit

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

    from apps.api.app.services.agents.prompts import optimization_advisor as P
    built = P.build(topic, feasibility, innovations, baselines, parallels)
    result: dict[str, Any] | None = None
    prov = "fast_json"
    try:
        if _use_unified():
            from apps.api.app.services.router import call_with_contract
            from apps.api.app.services.router.model_policy import TaskRole
            from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
            register_graph_contracts()
            contract_result = call_with_contract(
                built["user"],
                system=built["system"],
                contract_id="optimization-advisory/v1",
                task_role=TaskRole.evidence_critic,
                max_tokens=2000,
                timeout=30,
            )
            prov = "unified_router"
            if contract_result.success and isinstance(contract_result.content, dict):
                result = contract_result.content
            else:
                logger.warning("optimization_advisor unified_router failed: %s", contract_result.error)
                result = _heuristic(state)
                prov = "heuristic"
        else:
            from apps.api.app.services import llm_router
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
                  [{"tool": "optimization-advisory/v1" if prov == "unified_router" else ("heuristic" if prov == "heuristic" else "optimization_advisor.llm")}],
                  prov, [],
                  state_keys=["optimization_directions", "trace_events"])
    # Re3.0 Fix 2.2: do NOT increment narrative_revision_count here;
    # only narrative_builder increments it to avoid double counting.
    return {"optimization_directions": result,
            "trace_events": [trace]}
