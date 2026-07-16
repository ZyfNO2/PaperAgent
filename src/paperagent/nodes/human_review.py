from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_services
from paperagent.schemas import HumanAction
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "human_review_node"


async def human_review_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    request = state.get("request")
    run = state.get("run")
    if request is None or run is None:
        raise ValueError("request and run are required")
    plan = state.get("plan")
    quality = state.get("quality")
    if quality is not None and quality.verdict == "human_review":
        question = quality.human_question or "Human review is required."
        source: Literal["planning", "quality"] = "quality"
    elif plan is not None and plan.status == "need_human":
        question = plan.clarification_question or "Clarification is required."
        source = "planning"
    else:
        raise ValueError("no active human-review request")
    action = HumanAction(
        action_id=f"{run.run_id}:human-review",
        question=question,
        source=source,
    )
    answer = interrupt(action.model_dump(mode="json"))
    if isinstance(answer, Mapping):
        answer_text = str(answer.get("answer", "")).strip()
    else:
        answer_text = str(answer).strip()
    if not answer_text:
        raise ValueError("human review answer must not be empty")
    updated_request = request.model_copy(update={"clarification_answer": answer_text})
    trace = [
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.started",
            status="started",
            input_payload=action,
        ),
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.completed",
            status="completed",
            output_payload={"answer_hash_only": answer_text},
        ),
    ]
    execution = execution_with(state, node=NODE, status="running")
    execution = execution.model_copy(update={"human_action_required": None})
    return {"request": updated_request, "execution": execution, "trace": trace}
