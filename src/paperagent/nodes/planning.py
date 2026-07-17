from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.schemas import ResearchPlan
from paperagent.state import PaperAgentState, StatePatch

NODE = "planning_node"


async def planning_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    request = state.get("request")
    run = state.get("run")
    if request is None or run is None:
        raise ValueError("request and run are required")

    def validate(plan: ResearchPlan) -> None:
        try:
            plan.validate_query_budget(
                run.budgets.max_queries_per_round * run.budgets.max_retrieval_rounds
            )
        except ValueError as exc:
            raise NodeError(code="SEMANTIC_PLAN_INVALID", message=str(exc), node=NODE) from exc

    patch, result = await call_structured(
        state=state,
        config=config,
        node=NODE,
        task="planning",
        schema=ResearchPlan,
        user_payload={
            "request": request.model_dump(mode="json"),
            "budgets": run.budgets.model_dump(mode="json"),
            "available_source_types": ["paper", "dataset", "repository", "web", "user_material"],
        },
        semantic_validate=validate,
    )
    if result is not None:
        patch["plan"] = result
    return patch


def planning_route(state: PaperAgentState) -> str:
    execution = state.get("execution")
    if execution is not None and execution.status == "failed":
        return "blocked"
    plan = state.get("plan")
    if plan is None:
        raise ValueError("plan is required for planning route")
    # Defensive: real LLMs may return a plan.status that the graph's
    # conditional_edges does not map (e.g. "draft"). Route any unknown status
    # to "blocked" so the graph always reaches report_node -> persist_node
    # instead of silently stopping after planning.
    if plan.status not in ("ready", "need_human", "blocked"):
        return "blocked"
    return plan.status
