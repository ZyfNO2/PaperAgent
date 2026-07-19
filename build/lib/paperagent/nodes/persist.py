from __future__ import annotations

from typing import Literal

from langchain_core.runnables import RunnableConfig

from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_services
from paperagent.state import PaperAgentState, StatePatch, state_to_primitive
from paperagent.telemetry import make_event

NODE = "persist_node"


async def persist_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    run = state.get("run")
    if run is None:
        raise ValueError("run is required")
    trace = [make_event(services, state, node=NODE, event_type="node.started", status="started")]
    key = f"{run.run_id}:final"
    await services.store.save(key, state_to_primitive(state))
    report = state.get("report")
    status: Literal["blocked", "completed"] = (
        "blocked" if report is None or report.status == "blocked" else "completed"
    )
    execution = execution_with(state, node=NODE, status=status)
    trace.append(
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.completed",
            status="completed",
            output_payload={"key": key, "status": status},
        )
    )
    return {"execution": execution, "trace": trace}
