from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.runtime import get_option
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery
from paperagent.state import PaperAgentState, StatePatch

NODE = "planning_node"


def _normalize_nonblocking_clarification(plan: ResearchPlan) -> ResearchPlan:
    """Continue bounded retrieval when the planner already supplied a complete query contract.

    A clarification can remain useful without blocking public-evidence retrieval. We only
    promote ``need_human`` when concrete evidence gaps and valid search queries are already
    present; plans without that contract still route to human review or block as before.
    """

    if plan.status != "need_human" or not plan.evidence_gaps or not plan.search_queries:
        return plan
    known_gaps = {gap.gap_id for gap in plan.evidence_gaps}
    if any(query.gap_id not in known_gaps for query in plan.search_queries):
        return plan
    return plan.model_copy(update={"status": "ready"})


def _unique_identifier(base: str, existing: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    existing.add(candidate)
    return candidate


def _material_title(reference: str) -> str:
    return reference.split(" [declared role:", 1)[0].strip()


def _ensure_user_material_identity_queries(
    plan: ResearchPlan,
    request: ResearchRequest,
    *,
    query_budget: int,
) -> ResearchPlan:
    """Ensure public user-supplied titles receive identity and role verification.

    This only adds exact-title public searches. It does not accept the material, infer
    compatibility, or turn an unidentified generic reference into evidence.
    """

    if plan.status == "blocked" or not request.user_material_refs:
        return plan
    gaps = list(plan.evidence_gaps)
    queries = list(plan.search_queries)
    existing_gap_ids = {gap.gap_id for gap in gaps}
    existing_query_ids = {query.query_id for query in queries}
    existing_query_text = " ".join(query.query.casefold() for query in queries)

    for index, reference in enumerate(request.user_material_refs, start=1):
        title = _material_title(reference)
        if not title or title.casefold() in existing_query_text:
            continue
        if len(queries) >= query_budget:
            break
        gap_id = _unique_identifier(f"user-material-{index:02d}-identity", existing_gap_ids)
        query_id = _unique_identifier(f"user-material-{index:02d}-lookup", existing_query_ids)
        gaps.append(
            EvidenceGap(
                gap_id=gap_id,
                description=(
                    "Verify the public identity, method details, declared role, and task "
                    f"compatibility of the user-supplied material titled {title!r}."
                ),
                required=True,
                minimum_accepted_items=1,
            )
        )
        queries.append(
            SearchQuery(
                query_id=query_id,
                gap_id=gap_id,
                query=title,
                source_types=["paper", "repository"],
            )
        )
        existing_query_text = f"{existing_query_text} {title.casefold()}"

    if len(queries) == len(plan.search_queries):
        return plan
    return plan.model_copy(
        update={
            "evidence_gaps": gaps,
            "search_queries": queries,
            "status": "ready" if plan.status == "need_human" else plan.status,
        }
    )


async def planning_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    request = state.get("request")
    run = state.get("run")
    if request is None or run is None:
        raise ValueError("request and run are required")
    query_budget = run.budgets.max_queries_per_round * run.budgets.max_retrieval_rounds

    def validate(plan: ResearchPlan) -> None:
        try:
            plan.validate_query_budget(query_budget)
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
        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_materials)
    return patch


def planning_route(state: PaperAgentState, config: RunnableConfig) -> str:
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
    if (
        plan.status == "need_human"
        and get_option(config, "human_review_policy", "interrupt") == "block"
    ):
        return "blocked"
    return plan.status
