from __future__ import annotations

from typing import Literal, cast

from langchain_core.runnables import RunnableConfig

from paperagent.runtime import get_option, get_services
from paperagent.schemas import (
    EvidenceBundle,
    ExecutionMeta,
    ResearchRequest,
    RetrievalState,
    RunBudgets,
    RunContext,
)
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "intake_node"


async def intake_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    raw_request = state.get("request")
    if raw_request is None:
        raise ValueError("request is required")
    request = ResearchRequest.model_validate(
        raw_request.model_dump() if isinstance(raw_request, ResearchRequest) else raw_request
    )
    budgets_raw = get_option(config, "budgets", RunBudgets())
    budgets = (
        budgets_raw
        if isinstance(budgets_raw, RunBudgets)
        else RunBudgets.model_validate(budgets_raw)
    )
    network_policy_raw = get_option(config, "network_policy", "offline")
    if network_policy_raw not in {"offline", "allow_search"}:
        raise ValueError("network_policy must be offline or allow_search")
    network_policy = cast(Literal["offline", "allow_search"], network_policy_raw)
    run = RunContext(
        run_id=services.ids.new_id("run"),
        thread_id=services.ids.new_id("thread"),
        created_at=services.clock.now(),
        model_profile=getattr(services.llm, "model_name", "structured-provider"),
        network_policy=network_policy,
        budgets=budgets,
    )
    execution = ExecutionMeta(current_node=NODE, status="running")
    retrieval = RetrievalState(max_rounds=budgets.max_retrieval_rounds)
    started = make_event(
        services,
        state,
        node=NODE,
        event_type="node.started",
        status="started",
        input_payload=request,
    )
    event_state: PaperAgentState = {**state, "run": run}
    completed = make_event(
        services,
        event_state,
        node=NODE,
        event_type="node.completed",
        status="completed",
        output_payload={"request": request, "run": run},
    )
    return {
        "request": request,
        "run": run,
        "execution": execution,
        "retrieval": retrieval,
        "evidence": EvidenceBundle(),
        "trace": [started, completed],
    }
