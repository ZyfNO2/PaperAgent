from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.academic_methodology import audit_method_plan
from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_services
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "methodology_audit_node"


async def methodology_audit_node(
    state: PaperAgentState,
    config: RunnableConfig,
) -> StatePatch:
    services = get_services(config)
    method = state.get("method")
    if method is None:
        raise ValueError("method proposal is required before methodology audit")
    report = audit_method_plan(method.methodology_plan)
    trace = [
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.started",
            status="started",
        ),
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.completed",
            status="completed",
            output_payload=report.trace,
        ),
    ]
    return {
        "methodology_audit": report,
        "execution": execution_with(state, node=NODE),
        "trace": trace,
    }
