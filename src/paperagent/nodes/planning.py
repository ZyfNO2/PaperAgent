from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.nodes._shared import call_structured
from paperagent.runtime import get_option
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery
from paperagent.state import PaperAgentState, StatePatch
from paperagent.user_materials import UserMaterialIdentity, user_material_identities

NODE = "planning_node"
_BUDGET_NORMALIZATION_RISK = (
    "Planner output exceeded the runtime query budget; excess evidence gaps and queries were "
    "deterministically removed before retrieval."
)
_BASELINE_QUERY_ABSENT_RISK = (
    "No explicit development-baseline evidence gap was declared; baseline discovery remains "
    "available through dataset-linked parallel papers and later evidence review."
)
_BASELINE_ROLE_HINTS = (
    "baseline",
    "基线",
)


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


_PUBLIC_ASSET_QUERY_HINTS = (
    "baseline",
    "reproducible",
    "reproduction",
    "implementation",
    "repository",
    "code",
    "dataset",
    "基线",
    "复现",
    "实现",
    "代码",
    "数据集",
)


def _runtime_source_types(query: SearchQuery) -> SearchQuery:
    """Extend baseline discovery queries with public code/data lanes.

    Exact-title user-material queries are deliberately narrow identity lanes. Expanding a
    repository identity lookup into a dataset lookup changes its verification contract and can
    consume provider budget on unrelated assets, so those generated queries are preserved.
    """

    if query.gap_id.startswith("user-material-"):
        return query
    source_types = list(query.source_types)
    query_text = f"{query.gap_id} {query.query}".casefold()
    if any(hint in query_text for hint in _PUBLIC_ASSET_QUERY_HINTS):
        for source_type in ("repository", "dataset"):
            if source_type not in source_types:
                source_types.append(source_type)
    if {"repository", "dataset"}.intersection(source_types) and "web" not in source_types:
        source_types.append("web")
    if source_types == query.source_types:
        return query
    return query.model_copy(update={"source_types": source_types})


def _normalize_plan_to_query_budget(plan: ResearchPlan, *, query_budget: int) -> ResearchPlan:
    """Bound an otherwise valid LLM plan instead of failing the entire research run.

    We keep one query for each declared gap in plan order before allocating remaining slots to
    additional queries. If the planner declared more gaps than the runtime can search, only the
    earliest budget-coverable gaps remain and the loss of scope is recorded as a risk.
    """

    normalized_queries = [_runtime_source_types(query) for query in plan.search_queries]
    if plan.status == "blocked" or len(normalized_queries) <= query_budget:
        if normalized_queries == plan.search_queries:
            return plan
        return plan.model_copy(update={"search_queries": normalized_queries})

    queries_by_gap: dict[str, list[SearchQuery]] = {}
    for query in normalized_queries:
        queries_by_gap.setdefault(query.gap_id, []).append(query)

    selected: list[SearchQuery] = []
    selected_ids: set[str] = set()
    for gap in plan.evidence_gaps:
        candidates = queries_by_gap.get(gap.gap_id, [])
        if not candidates or len(selected) >= query_budget:
            continue
        query = candidates[0]
        selected.append(query)
        selected_ids.add(query.query_id)

    for query in normalized_queries:
        if len(selected) >= query_budget:
            break
        if query.query_id in selected_ids:
            continue
        selected.append(query)
        selected_ids.add(query.query_id)

    selected_gap_ids = {query.gap_id for query in selected}
    selected_gaps = [gap for gap in plan.evidence_gaps if gap.gap_id in selected_gap_ids]
    risks = list(plan.risks)
    if _BUDGET_NORMALIZATION_RISK not in risks:
        risks.append(_BUDGET_NORMALIZATION_RISK)
    return plan.model_copy(
        update={
            "evidence_gaps": selected_gaps,
            "search_queries": selected,
            "risks": risks,
        }
    )


def _unique_identifier(base: str, existing: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    existing.add(candidate)
    return candidate


def _contains_baseline_role(value: str) -> bool:
    normalized = value.casefold()
    return any(hint in normalized for hint in _BASELINE_ROLE_HINTS)


def _ensure_baseline_role_query(
    plan: ResearchPlan,
    *,
    query_budget: int,
) -> ResearchPlan:
    """Guarantee an explicit baseline retrieval role without displacing identity queries."""

    if plan.status == "blocked" or not plan.search_queries:
        return plan
    if any(_contains_baseline_role(query.query) for query in plan.search_queries):
        return plan

    baseline_gap_ids = {
        gap.gap_id
        for gap in plan.evidence_gaps
        if _contains_baseline_role(f"{gap.gap_id} {gap.description}")
    }
    for index, query in enumerate(plan.search_queries):
        if query.gap_id not in baseline_gap_ids:
            continue
        rewritten = query.model_copy(
            update={
                "query": f"{query.query} reproducible baseline comparator implementation",
            }
        )
        queries = list(plan.search_queries)
        queries[index] = _runtime_source_types(rewritten)
        return plan.model_copy(update={"search_queries": queries})

    del query_budget
    risks = list(plan.risks)
    if _BASELINE_QUERY_ABSENT_RISK not in risks:
        risks.append(_BASELINE_QUERY_ABSENT_RISK)
    return plan.model_copy(update={"risks": risks})


def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
    normalized_title = " ".join(title.replace('"', " ").split()).casefold()
    normalized_query = " ".join(query.query.replace('"', " ").split()).casefold()
    return bool(normalized_title and normalized_title in normalized_query)


def _ensure_user_material_identity_queries(
    plan: ResearchPlan,
    request: ResearchRequest,
    *,
    query_budget: int,
) -> ResearchPlan:
    """Prioritize exact-title verification for identifiable public supplied materials.

    Generic upload placeholders stay unverified. The function does not accept a material or infer
    compatibility; it only creates explicit identity-and-role evidence gaps. Identity queries are
    prepended and the merged plan is normalized afterwards, so a planner that consumes the entire
    query budget cannot crowd out verification of user-declared papers.
    """

    if plan.status == "blocked" or not request.user_material_refs:
        return plan

    existing_gap_ids = {gap.gap_id for gap in plan.evidence_gaps}
    existing_query_ids = {query.query_id for query in plan.search_queries}
    identities = [
        identity
        for identity in user_material_identities(request.user_material_refs)
        if identity.identifiable
    ]
    if not identities:
        return plan

    identity_gaps: list[EvidenceGap] = []
    identity_queries: list[SearchQuery] = []
    queued_identities: list[tuple[UserMaterialIdentity, str, str]] = []

    for identity in identities:
        if len(identity_queries) >= query_budget:
            break
        if any(
            _query_contains_material_title(query, identity.title)
            and "paper" in query.source_types
            for query in plan.search_queries
        ):
            continue
        gap_id = _unique_identifier(identity.gap_id, existing_gap_ids)
        query_id = _unique_identifier(identity.query_id, existing_query_ids)
        exact_title = identity.title.replace('"', " ").strip()
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
                query=f'"{exact_title}"',
                source_types=["paper", "web"],
            )
        )
        queued_identities.append((identity, gap_id, exact_title))

    for identity, gap_id, exact_title in queued_identities:
        if len(identity_queries) >= query_budget:
            break
        if any(
            _query_contains_material_title(query, identity.title)
            and "repository" in query.source_types
            for query in plan.search_queries
        ):
            continue
        repository_query_id = _unique_identifier(
            f"{identity.query_id}-implementation", existing_query_ids
        )
        identity_queries.append(
            SearchQuery(
                query_id=repository_query_id,
                gap_id=gap_id,
                query=f'"{exact_title}" official implementation code repository',
                source_types=["repository", "web"],
            )
        )

    if not identity_queries:
        return plan
    merged = plan.model_copy(
        update={
            "evidence_gaps": [*identity_gaps, *plan.evidence_gaps],
            "search_queries": [*identity_queries, *plan.search_queries],
            "status": "ready" if plan.status == "need_human" else plan.status,
        }
    )
    return _normalize_plan_to_query_budget(merged, query_budget=query_budget)


async def planning_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    request = state.get("request")
    run = state.get("run")
    if request is None or run is None:
        raise ValueError("request and run are required")
    query_budget = run.budgets.max_queries_per_round * run.budgets.max_retrieval_rounds

    def normalize(plan: ResearchPlan) -> ResearchPlan:
        return _normalize_plan_to_query_budget(plan, query_budget=query_budget)

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
            "available_source_types": [
                "paper",
                "dataset",
                "repository",
                "web",
                "user_material",
            ],
        },
        transform=normalize,
        semantic_validate=validate,
    )
    if result is not None:
        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        with_baseline_query = _ensure_baseline_role_query(
            with_materials,
            query_budget=query_budget,
        )
        bounded = _normalize_plan_to_query_budget(
            with_baseline_query,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(bounded)
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
