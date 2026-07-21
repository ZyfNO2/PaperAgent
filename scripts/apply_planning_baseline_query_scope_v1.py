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


def main() -> int:
    replace_once(
        PLANNING,
        '''_BASELINE_QUERY_BUDGET_RISK = (
    "No explicit baseline/comparator query could be added because the runtime query budget was "
    "already fully allocated to required evidence gaps."
)
''',
        '''_BASELINE_QUERY_ABSENT_RISK = (
    "No explicit baseline/comparator evidence gap was declared; baseline discovery remains "
    "available through dataset-linked parallel papers and later evidence review."
)
''',
        "baseline absence risk",
    )
    replace_once(
        PLANNING,
        '''def _baseline_query_text(plan: ResearchPlan) -> str:
    topic = plan.problem_statement.strip() or plan.scope.strip()
    return (
        f"{topic} task-matched reproducible baseline comparator implementation "
        "benchmark comparison"
    )


''',
        "",
        "remove unconditional baseline query builder",
    )
    replace_once(
        PLANNING,
        '''    if len(plan.search_queries) >= query_budget:
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
''',
        '''    del query_budget
    risks = list(plan.risks)
    if _BASELINE_QUERY_ABSENT_RISK not in risks:
        risks.append(_BASELINE_QUERY_ABSENT_RISK)
    return plan.model_copy(update={"risks": risks})
''',
        "no unconditional baseline gap",
    )
    replace_once(
        TEST,
        '''def test_baseline_query_completion_adds_gap_when_budget_allows() -> None:
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
''',
        '''def test_baseline_query_completion_does_not_add_gap_without_role_contract() -> None:
    from paperagent.nodes.planning import (
        _BASELINE_QUERY_ABSENT_RISK,
        _ensure_baseline_role_query,
    )
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
    assert updated.search_queries == plan.search_queries
    assert updated.evidence_gaps == plan.evidence_gaps
    assert _BASELINE_QUERY_ABSENT_RISK in updated.risks
''',
        "no new gap test",
    )
    replace_once(
        TEST,
        '''    from paperagent.nodes.planning import (
        _BASELINE_QUERY_BUDGET_RISK,
        _ensure_baseline_role_query,
    )
''',
        '''    from paperagent.nodes.planning import (
        _BASELINE_QUERY_ABSENT_RISK,
        _ensure_baseline_role_query,
    )
''',
        "risk import",
    )
    replace_once(
        TEST,
        '''    assert _BASELINE_QUERY_BUDGET_RISK in updated.risks
''',
        '''    assert _BASELINE_QUERY_ABSENT_RISK in updated.risks
''',
        "risk assertion",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
