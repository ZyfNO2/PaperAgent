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
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        from apps.api.app.services.agents.prompts import narrative_builder as P
        built = P.build(topic, innovations, feasibility)
        out = call_json_with_validation(
            built["user"],
            system=built["system"],
            node_name="narrative_builder",
            profile="fast_json",
            max_tokens=2000,
            timeout=30,
            fallback=_heuristic(state),
        )
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("narrative_builder LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    # Re4.3: Append-only revision history
    current_count = state.get("narrative_revision_count", 0)
    revision_id = f"rev-{current_count}"
    parent_id = f"rev-{current_count - 1}" if current_count > 0 else None

    revision = {
        "revision_id": revision_id,
        "parent_revision_id": parent_id,
        "three_problems": result.get("three_problems", []),
        "nick_model_name": result.get("nick_model_name"),
        "narrative_summary": result.get("narrative_summary"),
        "chapter_outline": result.get("chapter_outline"),
        "abstract_draft": result.get("abstract_draft"),
        "revision_reason": state.get("_narrative_revision_reason") or "initial",
        "revision_source": state.get("_narrative_revision_source") or "initial",
        "diff": None,
    }

    revisions = list(state.get("narrative_revisions") or [])
    if revisions:
        prev = revisions[-1]
        revision["diff"] = _compute_diff(prev, result)
    revisions_out = revisions + [revision]

    trace = _emit("narrative_builder", t0,
                  {"n_innovation": len(innovations)},
                  {"nick_model_name": result.get("nick_model_name", "")},
                  [{"tool": "narrative_builder.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["research_narrative", "narrative_revisions",
                              "narrative_revision_count", "trace_events"])
    return {"research_narrative": result,
            "narrative_revisions": revisions_out,
            "narrative_revision_count": current_count + 1,
            "trace_events": [trace]}


def _compute_diff(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    """Compute simple diff between two narrative revisions."""
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for key in ("nick_model_name", "narrative_summary", "abstract_draft"):
        old_val = prev.get(key, "") or ""
        new_val = curr.get(key, "") or ""
        if old_val != new_val:
            changed.append({"field": key, "old: ": old_val[:100], "new": new_val[:100]})
    old_problems = prev.get("three_problems") or []
    new_problems = curr.get("three_problems") or []
    if len(new_problems) > len(old_problems):
        added.append({"field": "three_problems", "count": len(new_problems) - len(old_problems)})
    elif len(new_problems) < len(old_problems):
        removed.append({"field": "three_problems", "count": len(old_problems) - len(new_problems)})
    return {"added": added, "removed": removed, "changed": changed}
