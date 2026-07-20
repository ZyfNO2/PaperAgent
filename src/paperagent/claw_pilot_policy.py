from __future__ import annotations

from paperagent.state import PaperAgentState

_GENERIC_SUPPLIED_TITLE_MARKERS = (
    "user-supplied",
    "uploaded paper",
    "unnamed paper",
    "unidentified paper",
    "unknown paper",
    "用户上传",
    "未命名论文",
    "未知论文",
)

_FOUNDATIONAL_SELECTION_MARKERS = (
    "无法设计可执行的实验计划",
    "cannot design an executable experiment",
    "cannot define an executable experiment",
    "specific organ",
    "organ or tissue",
    "target organ",
    "具体器官",
    "组织类型",
)


def infer_benchmark_pilot_override(state: PaperAgentState) -> bool | None:
    """Return ``False`` only when an unresolved input makes a pilot premature.

    ``None`` delegates to the existing benchmark-normalization heuristic. This keeps
    bounded pilots available for ordinary metric, compute, or business-priority
    unknowns while preventing a pilot when the experimental target itself or the
    identity of a supplied core method is still undefined.
    """

    request = state.get("request")
    if request is not None and request.clarification_answer:
        return None

    if request is not None:
        for reference in request.user_material_refs:
            title = reference.split("[declared role:", maxsplit=1)[0].strip().casefold()
            if any(marker in title for marker in _GENERIC_SUPPLIED_TITLE_MARKERS):
                return False

    plan = state.get("plan")
    if plan is None:
        return None
    unresolved_text = " ".join(
        (
            plan.clarification_question or "",
            *plan.risks,
        )
    ).casefold()
    if any(marker in unresolved_text for marker in _FOUNDATIONAL_SELECTION_MARKERS):
        return False
    return None


__all__ = ["infer_benchmark_pilot_override"]
