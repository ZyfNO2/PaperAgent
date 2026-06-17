"""LangGraph real-graph end-to-end tests.

These tests actually ``.invoke()`` the compiled StateGraph, walking through
IntakeNode → IntakeValidationNode → {TopicDecompositionNode | HumanClarificationNode | END}
and asserting the state shape after each path.
"""

from __future__ import annotations

from typing import Any

import pytest

from packages.agents.graphs.intake_graph import build_intake_graph
from packages.domain import (
    InheritedResource,
    MissingField,
    ProjectIntake,
    StudentResourceProfile,
    ValidationOutcome,
)


def _msg_role(m: Any) -> str | None:
    """从 SystemMessage / dict / 其他消息对象中抽出 role。"""

    if isinstance(m, dict):
        return m.get("role")
    return getattr(m, "type", None)


def _msg_content(m: Any) -> str:
    if isinstance(m, dict):
        return m.get("content", "")
    return getattr(m, "content", "")


def _complete(case_id: str = "GRAPH_OK") -> ProjectIntake:
    return ProjectIntake.model_validate(
        {
            "case_id": case_id,
            "major": "计算机科学与技术",
            "degree_type": "硕士",
            "goal_level": "保毕业",
            "thesis_deadline": "2027-06-01",
            "proposal_deadline": "2026-10-15",
            "first_result_deadline": "2026-12-31",
            "advisor_direction": "图神经网络",
            "school_requirements": ["必须中文文献"],
            "inherited_resources": [
                InheritedResource(
                    kind="同门毕业论文",
                    description="师兄论文",
                    available=True,
                )
            ],
            "student_resources": StudentResourceProfile(
                compute_resource="笔记本 3060", weekly_hours=25
            ),
            "raw_topic": "基于图神经网络的学术论文推荐",
            "must_keep": ["图神经网络"],
            "can_drop": [],
            "missing_fields": [],
            "intake_rating": "A",
        }
    )


def _missing_one_p0(case_id: str = "GRAPH_C") -> ProjectIntake:
    """丢一个 P0 → 评级 C（NEED_CLARIFICATION）。"""

    return _complete(case_id=case_id).model_copy(
        update={"proposal_deadline": None}
    )


def _placeholder(case_id: str = "GRAPH_D") -> ProjectIntake:
    return ProjectIntake.model_validate(
        {
            "case_id": case_id,
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        }
    )


def _state_for(intake: ProjectIntake) -> dict:
    return {"intake": intake}


def test_graph_routes_OK_to_topic_decomposition() -> None:
    graph = build_intake_graph()
    result = graph.invoke(_state_for(_complete()))

    assert result["validation_outcome"] == ValidationOutcome.OK.value
    assert result["intake_rating"] == "A"
    assert result["ready_for_phase02"] is True
    assert result["needs_clarification"] is False
    assert result["blocked"] is False
    # messages accumulate across nodes via add_messages reducer
    assert any(_msg_role(m) == "system" for m in result.get("messages", []))


def test_graph_routes_NEED_CLARIFICATION_to_human_node() -> None:
    graph = build_intake_graph()
    intake = _missing_one_p0()
    result = graph.invoke(_state_for(intake))

    assert result["validation_outcome"] == ValidationOutcome.NEED_CLARIFICATION.value
    assert result["intake_rating"] == "C"
    assert result["needs_clarification"] is True
    assert result["ready_for_phase02"] is False
    assert result["blocked"] is False
    assert any(
        (m.field_name if isinstance(m, MissingField) else m["field_name"])
        == "proposal_deadline"
        for m in result["missing_fields"]
    )


def test_graph_routes_BLOCKED_to_END() -> None:
    graph = build_intake_graph()
    result = graph.invoke(_state_for(_placeholder()))

    assert result["validation_outcome"] == ValidationOutcome.BLOCKED.value
    assert result["intake_rating"] == "D"
    assert result["blocked"] is True
    assert result["ready_for_phase02"] is False
    assert result["needs_clarification"] is False
    # 至少记录 6 个 missing 字段
    assert len(result["missing_fields"]) >= 6


def test_graph_clarification_then_full_re_runs_to_A() -> None:
    """模拟 HumanClarificationNode 之后再走一次图。

    Phase 01 的 LangGraph 图不会自动循环补问（那是后续工作）。这里
    验证：当 ``intake`` 本身被补齐后再 invoke，状态机正确走到
    TopicDecompositionNode。
    """

    graph = build_intake_graph()
    # 第一次：占位 → D
    first = graph.invoke(_state_for(_placeholder(case_id="GRAPH_LOOP")))
    assert first["intake_rating"] == "D"

    # 模拟补问：拿一个完整 intake，重新 invoke
    second = graph.invoke(_state_for(_complete(case_id="GRAPH_LOOP")))
    assert second["intake_rating"] == "A"
    assert second["validation_outcome"] == ValidationOutcome.OK.value


@pytest.mark.parametrize(
    "rating,expected_outcome",
    [
        ("A", ValidationOutcome.OK.value),
        ("B", ValidationOutcome.OK.value),
        ("C", ValidationOutcome.NEED_CLARIFICATION.value),
        ("D", ValidationOutcome.BLOCKED.value),
    ],
)
def test_graph_routing_for_each_rating(rating: str, expected_outcome: str) -> None:
    graph = build_intake_graph()
    if rating == "A":
        intake = _complete(case_id=f"G_{rating}")
    elif rating == "B":
        # 丢一个 P2 must_keep → B
        intake = _complete(case_id=f"G_{rating}").model_copy(update={"must_keep": []})
    elif rating == "C":
        intake = _missing_one_p0(case_id=f"G_{rating}")
    else:  # D
        intake = _placeholder(case_id=f"G_{rating}")

    result = graph.invoke(_state_for(intake))
    assert result["intake_rating"] == rating
    assert result["validation_outcome"] == expected_outcome
