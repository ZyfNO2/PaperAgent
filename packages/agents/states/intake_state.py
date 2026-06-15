"""LangGraph state for Phase 01.

设计说明：TopicPilotState 是 TypedDict，理论上可被 LangGraph 之外的环境
（如纯 FastAPI 单元测试）直接使用。因此 reducer (``add_messages``) 通过
``getattr`` 在模块导入时惰性解析；缺 langgraph 时仍能构建状态字典。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict, get_type_hints


def _try_get_add_messages():
    """惰性导入 langgraph 的 add_messages reducer。

    缺失 langgraph 时返回 ``lambda a, b: a + b`` 退路，确保 Phase 01 在未
    装齐依赖的环境也能跑模型/校验测试。
    """

    try:
        from langgraph.graph.message import add_messages  # type: ignore

        return add_messages
    except Exception:
        def _fallback(left: list, right: list) -> list:
            return list(left) + list(right)
        return _fallback


_MESSAGES_REDUCER = _try_get_add_messages()


class TopicPilotState(TypedDict, total=False):
    """``TopicPilotGraph`` 的运行时状态。

    Phase 01 只用到 intake/rating/outcome/missing/questions；后续 Phase 会
    追加 topic_spec、papers、datasets、baselines、risk_score、pivots、
    work_packages、committee_review 等字段。
    """

    intake: Any  # ProjectIntake
    intake_rating: str  # IntakeRating
    validation_outcome: str  # ValidationOutcome
    missing_fields: list  # list[MissingField]

    messages: Annotated[list, _MESSAGES_REDUCER]

    needs_clarification: bool
    blocked: bool
    ready_for_phase02: bool


def state_field_names() -> list[str]:
    """供 LangGraph 节点调试使用。"""

    return list(get_type_hints(TopicPilotState).keys())
