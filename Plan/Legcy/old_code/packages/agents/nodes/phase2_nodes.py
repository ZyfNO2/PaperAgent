"""Phase 02: Topic decomposition node for the LangGraph graph."""

from __future__ import annotations

from packages.agents.nodes.phase2_decompose import (
    allow_proceed_to_phase03,
    decompose,
)


def topic_decomposition_node(state: dict) -> dict:
    """LangGraph 节点：调 LLM 拆解题目，写 TopicSpec 进 state。

    state 必须含 ``intake``（ProjectIntake）。返回字典含
    ``topic_spec``、``decomposition_rating``、
    ``allow_proceed_to_phase03``。
    """

    intake = state["intake"]
    spec = decompose(intake, prefer=state.get("llm_prefer", "auto"))
    spec.project_id = state.get("project_id", "")
    allow, reason = allow_proceed_to_phase03(spec)
    return {
        "topic_spec": spec,
        "decomposition_rating": spec.decomposition_rating,
        "allow_proceed_to_phase03": allow,
        "block_reason": None if allow else reason,
        "needs_clarification": not allow,
        "ready_for_phase02": True,
    }
