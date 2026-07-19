from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from paperagent.errors import FixtureNotFoundError, NodeError, ProviderError
from paperagent.prompts import get_prompt
from paperagent.runtime import RuntimeServices, get_fixture_version, get_services, get_task_scenario
from paperagent.schemas import ExecutionMeta, Message, NodeErrorRecord
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

T = TypeVar("T", bound=BaseModel)
_UNSET = object()


def llm_call_index(services: RuntimeServices, task: str) -> int:
    calls = getattr(services.llm, "calls", [])
    return sum(1 for call in calls if getattr(getattr(call, "key", None), "task", None) == task)


def search_call_index(services: RuntimeServices, query_id: str) -> int:
    calls = getattr(services.search, "calls", [])
    return sum(
        1 for call in calls if getattr(getattr(call, "key", None), "query_id", None) == query_id
    )


def execution_with(
    state: PaperAgentState,
    *,
    node: str,
    status: Literal["running", "waiting_human", "completed", "blocked", "failed"] | None = None,
    llm_increment: int = 0,
    repair_increment: int = 0,
    repair_target: Literal["retrieval", "method"] | None = None,
    error: NodeErrorRecord | None | object = _UNSET,
) -> ExecutionMeta:
    current = state.get("execution", ExecutionMeta(status="running"))
    updates: dict[str, Any] = {
        "current_node": node,
        "status": status or current.status,
        "llm_call_count": current.llm_call_count + llm_increment,
        "repair_count": current.repair_count + repair_increment,
        "repair_target": repair_target,
    }
    if error is not _UNSET:
        updates["last_error"] = error
    return current.model_copy(update=updates)


def as_node_error(exc: Exception, *, node: str, default_code: str) -> NodeError:
    if isinstance(exc, ProviderError):
        return NodeError(
            code=exc.code,
            message=str(exc),
            node=node,
            retryable=exc.retryable,
            details={"provider": exc.provider, "task": exc.task},
        )
    if isinstance(exc, FixtureNotFoundError):
        return NodeError(code=exc.code, message=str(exc), node=node, retryable=False)
    if isinstance(exc, NodeError):
        return exc
    return NodeError(code=default_code, message=str(exc), node=node, retryable=False)


def json_message(payload: Any) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


async def call_structured(
    *,
    state: PaperAgentState,
    config: Mapping[str, Any] | None,
    node: str,
    task: str,
    schema: type[T],
    user_payload: Any,
    semantic_validate: Callable[[T], None] | None = None,
    scenario: str | None = None,
) -> tuple[StatePatch, T | None]:
    services = get_services(config)
    prompt = get_prompt(task)
    selected_scenario = scenario or get_task_scenario(config, task)
    fixture_version = get_fixture_version(config)
    call_index = llm_call_index(services, task)
    key = f"{task}/{selected_scenario}/{call_index}/{fixture_version}"
    messages = [
        Message(role="system", content=prompt.system),
        Message(role="user", content=json_message(user_payload)),
    ]
    trace = [
        make_event(
            services,
            state,
            node=node,
            event_type="node.started",
            status="started",
            input_payload=user_payload,
        ),
        make_event(
            services,
            state,
            node=node,
            event_type="llm.requested",
            status="started",
            input_payload=user_payload,
            prompt_version=prompt.version,
            fixture_key=key,
            model_name=getattr(services.llm, "model_name", None),
        ),
    ]
    try:
        result = await services.llm.generate_structured(
            task=task,
            scenario=selected_scenario,
            call_index=call_index,
            fixture_version=fixture_version,
            schema=schema,
            messages=messages,
        )
        if semantic_validate is not None:
            semantic_validate(result)
    except Exception as exc:
        error = as_node_error(exc, node=node, default_code="LLM_NODE_FAILED")
        trace.extend(
            [
                make_event(
                    services,
                    state,
                    node=node,
                    event_type="llm.failed",
                    status="failed",
                    prompt_version=prompt.version,
                    fixture_key=key,
                    error_code=error.code,
                ),
                make_event(
                    services,
                    state,
                    node=node,
                    event_type="node.failed",
                    status="failed",
                    error_code=error.code,
                ),
            ]
        )
        return (
            {
                "execution": execution_with(
                    state,
                    node=node,
                    status="failed",
                    llm_increment=1,
                    error=error.to_record(),
                ),
                "trace": trace,
            },
            None,
        )
    trace.extend(
        [
            make_event(
                services,
                state,
                node=node,
                event_type="llm.responded",
                status="completed",
                output_payload=result,
                prompt_version=prompt.version,
                fixture_key=key,
                model_name=getattr(services.llm, "model_name", None),
                token_usage=getattr(services.llm, "last_usage", None),
                duration_ms=getattr(services.llm, "last_latency_ms", None),
            ),
            make_event(
                services,
                state,
                node=node,
                event_type="node.completed",
                status="completed",
                output_payload=result,
            ),
        ]
    )
    return (
        {
            "execution": execution_with(state, node=node, llm_increment=1),
            "trace": trace,
        },
        result,
    )
