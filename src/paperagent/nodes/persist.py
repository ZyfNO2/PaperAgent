from __future__ import annotations

from typing import Literal

from langchain_core.runnables import RunnableConfig

from paperagent.nodes._shared import execution_with
from paperagent.outcome import audit_state_consistency, derive_final_outcome
from paperagent.runtime import get_services
from paperagent.schemas import NodeErrorRecord
from paperagent.state import PaperAgentState, StatePatch, state_to_primitive
from paperagent.telemetry import make_event

NODE = "persist_node"


def _execution_status(state: PaperAgentState) -> Literal["blocked", "completed", "failed"]:
    outcome = state.get("final_outcome") or derive_final_outcome(state)
    if outcome.execution_status == "failed":
        return "failed"
    if outcome.execution_status in {"blocked", "cancelled"} or outcome.report_status == "blocked":
        return "blocked"
    return "completed"


async def persist_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    run = state.get("run")
    if run is None:
        raise ValueError("run is required")
    final_outcome = state.get("final_outcome") or derive_final_outcome(state)
    audit_state: PaperAgentState = {**state, "final_outcome": final_outcome}
    trace_audit = audit_state_consistency(audit_state)
    status = _execution_status(audit_state)
    if trace_audit.passed:
        execution = execution_with(audit_state, node=NODE, status=status)
    else:
        status = "failed"
        error = NodeErrorRecord(
            code="TRACE_CONTRACT_FAILURE",
            message="trace and final artifacts violate deterministic state invariants",
            node=NODE,
            retryable=False,
            details={"invariants": trace_audit.error_codes},
        )
        execution = execution_with(
            audit_state,
            node=NODE,
            status=status,
            error=error,
        )
    trace = [
        make_event(
            services,
            audit_state,
            node=NODE,
            event_type="node.started",
            status="started",
        ),
        make_event(
            services,
            audit_state,
            node=NODE,
            event_type="trace.audited",
            status="completed" if trace_audit.passed else "failed",
            output_payload=trace_audit,
            error_code=None if trace_audit.passed else "TRACE_CONTRACT_FAILURE",
        ),
    ]
    persisted_state: PaperAgentState = {
        **audit_state,
        "trace_audit": trace_audit,
        "execution": execution,
    }
    key = f"{run.run_id}:final"
    await services.store.save(key, state_to_primitive(persisted_state))
    trace.append(
        make_event(
            services,
            audit_state,
            node=NODE,
            event_type="node.completed" if trace_audit.passed else "node.failed",
            status="completed" if trace_audit.passed else "failed",
            output_payload={"key": key, "status": status, "trace_audit": trace_audit},
            error_code=None if trace_audit.passed else "TRACE_CONTRACT_FAILURE",
        )
    )
    return {
        "final_outcome": final_outcome,
        "trace_audit": trace_audit,
        "execution": execution,
        "trace": trace,
    }
