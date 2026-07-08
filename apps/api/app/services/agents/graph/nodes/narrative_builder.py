"""narrative_builder — Re1.4 MVP node."""
import time
import logging
import re
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

from ._util import emit_trace as _emit

def _heuristic(state):
    topic = state.get("topic", "")
    baselines = state.get("baseline_candidates") or []
    b0 = (baselines[0].get("title", "") if baselines else "现有方法")
    words = re.findall(r'[A-Za-z]+', topic)
    nick = (words[0] + "-Net") if words else "Proposed-Net"
    return {
        "three_problems": [
            {"problem": f"{b0}在复杂场景下精度不足", "from_paper": b0},
            {"problem": "现有方法对小目标检测能力有限", "from_paper": b0},
            {"problem": "推理速度难以满足实时需求", "from_paper": b0}],
        "nick_model_name": nick,
        "narrative_summary": f"在{topic}中，现有方法存在三个问题。本文提出{nick}，"
                              f"通过改进模块解决上述问题。",
        "chapter_outline": {},
        "abstract_draft": ""
    }

def narrative_builder_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    innovations = state.get("innovation_points") or []
    feasibility = state.get("feasibility_report") or {}

    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import narrative_builder as P
        built = P.build(topic, innovations, feasibility)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("narrative_builder LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    trace = _emit("narrative_builder", t0,
                  {"n_innovation": len(innovations)},
                  {"nick_model_name": result.get("nick_model_name", "")},
                  [{"tool": "narrative_builder.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["research_narratives", "narrative_revision_count",
                              "trace_events"])
    current_count = state.get("narrative_revision_count", 0)
    # Re3.0 Fix 2.1: field name unified to research_narrative (singular)
    return {"research_narrative": result,
            "narrative_revision_count": current_count + 1,
            "trace_events": [trace]}
