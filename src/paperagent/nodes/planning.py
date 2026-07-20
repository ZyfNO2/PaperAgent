from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.runtime import get_option
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery
from paperagent.state import PaperAgentState, StatePatch
from paperagent.user_materials import user_material_identities

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


def _ensure_user_material_identity_queries(
    plan: ResearchPlan,
    request: ResearchRequest,
    *,
    query_budget: int,
) -> ResearchPlan:
    """Prioritize exact-title verification for identifiable public supplied materials.

    Generic upload placeholders stay unverified. The function does not accept a material or infer
    compatibility; it only creates explicit identity-and-role evidence gaps within the query budget.
    """

    if plan.status == "blocked" or not request.user_material_refs:
        return plan
    identity_gaps: list[EvidenceGap] = []
    identity_queries: list[SearchQuery] = []
    existing_gap_ids = {gap.gap_id for gap in plan.evidence_gaps}
    existing_query_ids = {query.query_id for query in plan.search_queries}
    available_slots = max(query_budget - len(plan.search_queries), 0)

    for identity in user_material_identities(request.user_material_refs):
        if not identity.identifiable or available_slots <= 0:
            continue
        gap_id = _unique_identifier(identity.gap_id, existing_gap_ids)
        query_id = _unique_identifier(identity.query_id, existing_query_ids)
        identity_gaps.append(
            EvidenceGap(
                gap_id=gap_id,
                description=(
                    "Verify the public identity, method details, declared role, and task "
                    f"compatibility of the user-supplied material titled {identity.title!r}."
                ),
                required=True,
                minimum_accepted_items=1,
            )
        )
        identity_queries.append(
            SearchQuery(
                query_id=query_id,
                gap_id=gap_id,
                query=identity.title,
                source_types=["paper", "repository"],
            )
        )
        available_slots -= 1

    if not identity_queries:
        return plan
    return plan.model_copy(
        update={
            "evidence_gaps": [*identity_gaps, *plan.evidence_gaps],
            "search_queries": [*identity_queries, *plan.search_queries],
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
    if plan.status not in ("ready", "need_human", "blocked"):
        return "blocked"
    if (
        plan.status == "need_human"
        and get_option(config, "human_review_policy", "interrupt") == "block"
    ):
        return "blocked"
    return plan.status
