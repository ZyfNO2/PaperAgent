from __future__ import annotations

from pathlib import Path

PLANNING = Path("src/paperagent/nodes/planning.py")
TEST = Path("tests/nodes/test_intake_planning.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{path}: missing {label}")
    path.write_text(source, encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    source = path.read_text(encoding="utf-8")
    if marker not in source:
        source += addition
    path.write_text(source, encoding="utf-8")


def main() -> int:
    replace_once(
        PLANNING,
        '''_BUDGET_NORMALIZATION_RISK = (
    "Planner output exceeded the runtime query budget; excess evidence gaps and queries were "
    "deterministically removed before retrieval."
)
''',
        '''_BUDGET_NORMALIZATION_RISK = (
    "Planner output exceeded the runtime query budget; excess evidence gaps and queries were "
    "deterministically removed before retrieval."
)
_BASELINE_QUERY_BUDGET_RISK = (
    "No explicit baseline/comparator query could be added because the runtime query budget was "
    "already fully allocated to required evidence gaps."
)
_BASELINE_ROLE_HINTS = (
    "baseline",
    "comparator",
    "comparison",
    "基线",
    "对照",
    "比较",
    "对比",
)
''',
        "baseline planning constants",
    )
    replace_once(
        PLANNING,
        '''def _ensure_user_material_identity_queries(
''',
        '''def _contains_baseline_role(value: str) -> bool:
    normalized = value.casefold()
    return any(hint in normalized for hint in _BASELINE_ROLE_HINTS)


def _baseline_query_text(plan: ResearchPlan) -> str:
    topic = plan.problem_statement.strip() or plan.scope.strip()
    return (
        f"{topic} task-matched reproducible baseline comparator implementation "
        "benchmark comparison"
    )


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

    if len(plan.search_queries) >= query_budget:
        risks = list(plan.risks)
        if _BASELINE_QUERY_BUDGET_RISK not in risks:
            risks.append(_BASELINE_QUERY_BUDGET_RISK)
        return plan.model_copy(update={"risks": risks})

    existing_gap_ids = {gap.gap_id for gap in plan.evidence_gaps}
    existing_query_ids = {query.query_id for query in plan.search_queries}
    gap_id = _unique_identifier("baseline-role-evidence", existing_gap_ids)
    query_id = _unique_identifier("baseline-role-query", existing_query_ids)
    baseline_gap = EvidenceGap(
        gap_id=gap_id,
        description=(
            "Identify a task-matched reproducible baseline or comparator and verify its "
            "implementation, evaluation contract, and task compatibility."
        ),
        required=True,
        minimum_accepted_items=1,
    )
    baseline_query = _runtime_source_types(
        SearchQuery(
            query_id=query_id,
            gap_id=gap_id,
            query=_baseline_query_text(plan),
            source_types=["paper"],
        )
    )
    return plan.model_copy(
        update={
            "evidence_gaps": [*plan.evidence_gaps, baseline_gap],
            "search_queries": [*plan.search_queries, baseline_query],
        }
    )


def _ensure_user_material_identity_queries(
''',
        "baseline query planning functions",
    )
    replace_once(
        PLANNING,
        '''        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_materials)
''',
        '''        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        with_baseline_query = _ensure_baseline_role_query(
            with_materials,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_baseline_query)
''',
        "planning node baseline query integration",
    )
    append_once(
        TEST,
        "test_baseline_query_completion_reuses_existing_gap_without_extra_query",
        '''


def test_baseline_query_completion_reuses_existing_gap_without_extra_query() -> None:
    from paperagent.nodes.planning import _ensure_baseline_role_query
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="industrial anomaly detection",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="baseline", description="baseline evidence")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="baseline",
                query="industrial anomaly detection methods",
                source_types=["paper"],
            )
        ],
    )
    updated = _ensure_baseline_role_query(plan, query_budget=10)
    assert len(updated.search_queries) == 1
    assert "baseline comparator" in updated.search_queries[0].query
    assert updated.search_queries[0].source_types == [
        "paper",
        "repository",
        "dataset",
        "web",
    ]


def test_baseline_query_completion_adds_gap_when_budget_allows() -> None:
    from paperagent.nodes.planning import _ensure_baseline_role_query
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="rare sensor failure classification",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="mechanism", description="failure mechanism")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="mechanism",
                query="rare sensor failure mechanism",
                source_types=["paper"],
            )
        ],
    )
    updated = _ensure_baseline_role_query(plan, query_budget=2)
    assert len(updated.search_queries) == 2
    added = updated.search_queries[-1]
    assert added.gap_id == "baseline-role-evidence"
    assert "reproducible baseline comparator" in added.query
    assert added.source_types == ["paper", "repository", "dataset", "web"]


def test_baseline_query_completion_records_budget_risk_without_eviction() -> None:
    from paperagent.nodes.planning import (
        _BASELINE_QUERY_BUDGET_RISK,
        _ensure_baseline_role_query,
    )
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="bounded task",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="mechanism", description="mechanism")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="mechanism",
                query="bounded mechanism evidence",
                source_types=["paper"],
            )
        ],
    )
    updated = _ensure_baseline_role_query(plan, query_budget=1)
    assert updated.search_queries == plan.search_queries
    assert _BASELINE_QUERY_BUDGET_RISK in updated.risks


def test_existing_baseline_role_query_is_not_rewritten() -> None:
    from paperagent.nodes.planning import _ensure_baseline_role_query
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    query = SearchQuery(
        query_id="q1",
        gap_id="g1",
        query="reproducible baseline implementation",
        source_types=["paper", "repository"],
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="task",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="task evidence")],
        search_queries=[query],
    )
    updated = _ensure_baseline_role_query(plan, query_budget=10)
    assert updated.search_queries == [query]
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
