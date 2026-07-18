from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import FixtureNotFoundError, ProviderError
from paperagent.nodes._shared import execution_with, search_call_index
from paperagent.runtime import get_fixture_version, get_search_scenario, get_services
from paperagent.schemas import SearchQuery, ToolErrorRecord
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "search_tool_node"


async def search_tool_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    retrieval = state.get("retrieval")
    if retrieval is None:
        raise ValueError("retrieval state is required")
    scenario = get_search_scenario(config)
    fixture_version = get_fixture_version(config)
    candidates = list(retrieval.raw_candidates)
    completed = list(retrieval.completed_query_ids)
    errors = list(retrieval.tool_errors)
    trace = [make_event(services, state, node=NODE, event_type="node.started", status="started")]
    for prepared in retrieval.prepared_queries:
        query = SearchQuery(
            query_id=prepared.query_id,
            gap_id=prepared.gap_id,
            query=prepared.query,
            source_types=prepared.source_types or ["web"],
        )
        index = search_call_index(services, query.query_id)
        trace.append(
            make_event(
                services,
                state,
                node=NODE,
                event_type="tool.requested",
                status="started",
                input_payload=query,
            )
        )
        try:
            found = await services.search.search(
                query=query,
                scenario=scenario,
                call_index=index,
                fixture_version=fixture_version,
                limit=10,
            )
            candidates.extend(found)
            if query.query_id not in completed:
                completed.append(query.query_id)
            result_reader = getattr(services.search, "last_provider_results", None)
            if callable(result_reader):
                for provider_result in result_reader(query.query_id):
                    if provider_result.status not in {"failed", "timeout", "rate_limited"}:
                        continue
                    errors.append(
                        ToolErrorRecord(
                            code=provider_result.error_code or "SEARCH_PROVIDER_ERROR",
                            message=provider_result.error_message
                            or f"{provider_result.provider} retrieval failed",
                            provider=provider_result.provider,
                            query_id=query.query_id,
                            retryable=provider_result.status in {"timeout", "rate_limited"},
                            attempt=provider_result.retry_count + 1,
                        )
                    )
            trace.append(
                make_event(
                    services,
                    state,
                    node=NODE,
                    event_type="tool.responded",
                    status="completed",
                    output_payload=found,
                )
            )
        except (ProviderError, FixtureNotFoundError) as exc:
            code = getattr(exc, "code", "SEARCH_PROVIDER_ERROR")
            errors.append(
                ToolErrorRecord(
                    code=code,
                    message=str(exc),
                    provider=getattr(services.search, "provider_name", "search"),
                    query_id=query.query_id,
                    retryable=getattr(exc, "retryable", False),
                    attempt=index + 1,
                )
            )
            trace.append(
                make_event(
                    services,
                    state,
                    node=NODE,
                    event_type="tool.failed",
                    status="failed",
                    error_code=code,
                )
            )
    updated = retrieval.model_copy(
        update={
            "raw_candidates": candidates,
            "completed_query_ids": completed,
            "tool_errors": errors,
            "prepared_queries": [],
        }
    )
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
