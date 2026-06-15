"""Phase 01 LangGraph skeleton.

拓扑：
    IntakeNode
    → IntakeValidationNode
    → 条件分支：
        NEED_CLARIFICATION → HumanClarificationNode → END
        BLOCKED            → END
        OK                 → TopicDecompositionNode → END

Phase 02 起，TopicDecompositionNode 之后会接 LiteratureSearchGraph /
DatasetSearchGraph / BaselineSearchGraph 等并行子图。
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from packages.agents.nodes import (
    human_clarification_node,
    intake_node,
    intake_validation_node,
    topic_decomposition_node,
)
from packages.agents.states import TopicPilotState
from packages.domain import ValidationOutcome


def _route_after_validation(state: TopicPilotState) -> str:
    outcome = state.get("validation_outcome")
    if outcome == ValidationOutcome.OK:
        return "topic_decomposition"
    if outcome == ValidationOutcome.NEED_CLARIFICATION:
        return "human_clarification"
    return "__end__"


def build_intake_graph():
    graph = StateGraph(TopicPilotState)

    graph.add_node("intake", intake_node)
    graph.add_node("intake_validation", intake_validation_node)
    graph.add_node("human_clarification", human_clarification_node)
    graph.add_node("topic_decomposition", topic_decomposition_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "intake_validation")

    graph.add_conditional_edges(
        "intake_validation",
        _route_after_validation,
        {
            "topic_decomposition": "topic_decomposition",
            "human_clarification": "human_clarification",
            "__end__": END,
        },
    )

    graph.add_edge("human_clarification", END)
    graph.add_edge("topic_decomposition", END)

    return graph.compile()
