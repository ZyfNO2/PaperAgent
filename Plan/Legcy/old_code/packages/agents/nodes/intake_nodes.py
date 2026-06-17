"""Intake / Validation / HumanClarification / TopicDecomposition nodes (Phase 01)."""

from __future__ import annotations

from typing import Any

from packages.domain import (
    ValidationOutcome,
    compute_intake_rating,
    derive_missing_fields,
    validate_intake,
)

from ..states import TopicPilotState


def _make_message(content: str, role: str = "system") -> Any:
    """构造 LangGraph 可识别的消息对象。

    优先用 ``langchain_core.messages``，缺包时回退到 ``dict``，
    任何情况下 ``add_messages`` reducer 都能累加。
    """

    try:
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        cls = {"system": SystemMessage, "human": HumanMessage, "ai": AIMessage}.get(
            role, SystemMessage
        )
        if role == "human":
            return HumanMessage(content=content)
        if role == "ai":
            return AIMessage(content=content)
        return SystemMessage(content=content)
    except Exception:
        return {"role": role, "content": content}


def intake_node(state: TopicPilotState) -> dict:
    """入口节点：保留 ProjectIntake，初始评分占位由 ValidationNode 覆盖。"""

    intake = state["intake"]
    return {
        "intake": intake,
        "missing_fields": list(intake.missing_fields),
        "intake_rating": intake.intake_rating,
        "validation_outcome": ValidationOutcome.OK,
        "needs_clarification": False,
        "blocked": False,
        "ready_for_phase02": False,
    }


def intake_validation_node(state: TopicPilotState) -> dict:
    """复用 domain 层 validate_intake，决定下一步走向。"""

    outcome, rating, missing = validate_intake(state["intake"])
    return {
        "validation_outcome": outcome,
        "intake_rating": rating,
        "missing_fields": missing,
        "needs_clarification": outcome == ValidationOutcome.NEED_CLARIFICATION,
        "blocked": outcome == ValidationOutcome.BLOCKED,
        "ready_for_phase02": outcome == ValidationOutcome.OK,
    }


def human_clarification_node(state: TopicPilotState) -> dict:
    """占位节点。

    Phase 01 不实现真实的多轮补问逻辑；它仅在 NEED_CLARIFICATION 时记录
    待补字段，等待用户重新触发 validate。后续 Phase 会接 LiteLLM 生成
    澄清问题。
    """

    return {
        "messages": [
            _make_message(
                "Phase 01 HumanClarificationNode 占位："
                f"待补 {len(state.get('missing_fields', []))} 个字段，"
                "待真实补问流程接入。",
                role="system",
            )
        ],
        "needs_clarification": True,
        "ready_for_phase02": False,
        "blocked": False,
    }


def topic_decomposition_node(state: TopicPilotState) -> dict:
    """Phase 02 占位节点。当前不修改状态，仅作为图末端哨兵。"""

    return {
        "ready_for_phase02": True,
        "needs_clarification": False,
        "blocked": False,
        "messages": [
            _make_message("TopicDecompositionNode 占位（Phase 02 实现）。", role="system")
        ],
    }


def derive_rating_preview(intake) -> str:
    """在 IntakeNode 之前快速预览评级，便于端到端测试。"""

    missing = derive_missing_fields(intake)
    return compute_intake_rating(intake, missing)
