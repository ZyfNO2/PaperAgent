from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.literature.query_refinement import refine_search_query
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
        gap_descriptions = {gap.gap_id: gap.description for gap in plan.evidence_gaps}
        request = state.get("request")
        research_context = " ".join(
            value
            for value in (
                request.question if request is not None else "",
                plan.problem_statement,
                plan.scope,
            )
            if value
        )
        prepared: list[PreparedQuery] = []
        for query in selected:
            gap_description = gap_descriptions.get(query.gap_id, "")
            refinement = refine_search_query(
                query.query,
                gap_id=query.gap_id,
                gap_description=gap_description,
                research_context=research_context,
            )
            prepared.append(
                PreparedQuery(
                    query_id=query.query_id,
                    gap_id=query.gap_id,
                    query=refinement.query,
                    original_query=query.query if refinement.changed else None,
                    refinement_reason=refinement.reason if refinement.changed else None,
                    removed_families=(
                        list(refinement.removed_families) if refinement.changed else []
                    ),
                    source_types=list(query.source_types),
                    round=next_round,
                )
            )
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
