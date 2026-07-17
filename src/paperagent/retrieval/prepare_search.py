from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_services
from paperagent.schemas import PreparedQuery, RetrievalState
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "prepare_search_node"


async def prepare_search_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    plan = state.get("plan")
    run = state.get("run")
    current = state.get("retrieval", RetrievalState())
    if plan is None or run is None:
        raise ValueError("plan and run are required")
    trace = [make_event(services, state, node=NODE, event_type="node.started", status="started")]
    if current.budget_exhausted or current.round >= current.max_rounds:
        updated = current.model_copy(update={"prepared_queries": [], "budget_exhausted": True})
    else:
        completed = set(current.completed_query_ids)
        available = [query for query in plan.search_queries if query.query_id not in completed]
        next_round = current.round + 1
        selected = available[: run.budgets.max_queries_per_round]
        prepared = [
            PreparedQuery(
                query_id=query.query_id,
                gap_id=query.gap_id,
                query=query.query,
                source_types=list(query.source_types),
                round=next_round,
            )
            for query in selected
        ]
        updated = current.model_copy(update={"round": next_round, "prepared_queries": prepared})
    trace.append(
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.completed",
            status="completed",
            output_payload=updated,
        )
    )
    return {"retrieval": updated, "execution": execution_with(state, node=NODE), "trace": trace}
