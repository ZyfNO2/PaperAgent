from __future__ import annotations

from copy import deepcopy

import pytest

from conftest import load_llm_raw


def _services(fixed_time, *, scenario="happy_path", failures=None):
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.testing import FixedClock, SequenceIdFactory

    fixtures = {
        FixtureKey(task="planning", scenario=scenario, call_index=0): load_llm_raw(
            "planning", scenario, 0
        )
    }
    return RuntimeServices(
        llm=FakeLLMProvider(fixtures=fixtures, failures=failures),
        search=FakeSearchProvider(fixtures={}),
        clock=FixedClock(fixed_time),
        ids=SequenceIdFactory(prefix="test"),
        store=InMemoryStateStore(),
    )


@pytest.mark.asyncio
async def test_intake_node__valid_request__initializes_bounded_state(
    fixed_time,
) -> None:
    from paperagent.nodes.intake import intake_node
    from paperagent.schemas import ResearchRequest

    state = {
        "request": ResearchRequest(
            question="  evaluate citations  ", required_constraints=["offline", "offline"]
        )
    }
    before = deepcopy(state)
    services = _services(fixed_time)
    patch = await intake_node(state, {"configurable": {"services": services}})
    assert patch["request"].question == "evaluate citations"
    assert patch["request"].required_constraints == ["offline"]
    assert patch["run"].budgets.max_retrieval_rounds == 2
    assert patch["execution"].status == "running"
    assert state == before
    assert [event.event_type for event in patch["trace"]] == [
        "node.started",
        "node.completed",
    ]


@pytest.mark.asyncio
async def test_planning_node__happy_fixture__returns_plan_and_usage_trace(
    fixed_time,
) -> None:
    from paperagent.nodes.intake import intake_node
    from paperagent.nodes.planning import planning_node
    from paperagent.schemas import ResearchRequest
    from paperagent.state import apply_state_patch

    services = _services(fixed_time)
    state = {"request": ResearchRequest(question="evaluate citations")}
    state = apply_state_patch(
        state, await intake_node(state, {"configurable": {"services": services}})
    )
    patch = await planning_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    assert patch["plan"].status == "ready"
    assert patch["execution"].llm_call_count == 1
    assert any(event.event_type == "llm.responded" for event in patch["trace"])
    assert any(event.prompt_version == "planning.v0.1.3" for event in patch["trace"])


@pytest.mark.asyncio
async def test_planning_node__provider_timeout__returns_typed_failure(
    fixed_time,
) -> None:
    from paperagent.errors import ProviderTimeoutError
    from paperagent.nodes.intake import intake_node
    from paperagent.nodes.planning import planning_node
    from paperagent.providers import FixtureKey
    from paperagent.schemas import ResearchRequest
    from paperagent.state import apply_state_patch

    key = FixtureKey(task="planning", scenario="happy_path", call_index=0)
    services = _services(
        fixed_time, failures={key: ProviderTimeoutError(provider="fake_llm", task="planning")}
    )
    state = {"request": ResearchRequest(question="evaluate citations")}
    state = apply_state_patch(
        state, await intake_node(state, {"configurable": {"services": services}})
    )
    patch = await planning_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    assert patch["execution"].status == "failed"
    assert patch["execution"].last_error.code == "PROVIDER_TIMEOUT"
    assert patch["trace"][-1].event_type == "node.failed"


def test_planning_route__status__maps_to_expected_edge() -> None:
    from paperagent.nodes.planning import planning_route
    from paperagent.schemas import ResearchPlan

    for status in ("ready", "need_human", "blocked"):
        kwargs = {
            "status": status,
            "problem_statement": "p",
            "scope": "s",
            "research_questions": [],
            "evidence_gaps": [],
            "search_queries": [],
            "success_criteria": [],
            "risks": [],
            "clarification_question": "question" if status == "need_human" else None,
            "block_reason": "blocked" if status == "blocked" else None,
        }
        if status == "ready":
            kwargs["research_questions"] = ["q"]
            kwargs["evidence_gaps"] = [{"gap_id": "g", "description": "d"}]
            kwargs["search_queries"] = [{"query_id": "q", "gap_id": "g", "query": "search"}]
        assert planning_route({"plan": ResearchPlan(**kwargs)}, {}) == status


def test_planning_route__headless_policy_blocks_human_interrupt() -> None:
    from paperagent.nodes.planning import planning_route
    from paperagent.schemas import ResearchPlan

    plan = ResearchPlan(
        status="need_human",
        problem_statement="p",
        scope="s",
        clarification_question="Which corpus should be used?",
    )
    assert (
        planning_route({"plan": plan}, {"configurable": {"human_review_policy": "block"}})
        == "blocked"
    )


def test_plan_normalization__oversized_plan__keeps_one_query_per_gap_then_fills() -> None:
    from paperagent.nodes.planning import (
        _BUDGET_NORMALIZATION_RISK,
        _normalize_plan_to_query_budget,
    )
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="bounded retrieval",
        scope="test",
        evidence_gaps=[
            EvidenceGap(gap_id=f"g{index}", description=f"gap {index}") for index in range(1, 7)
        ],
        search_queries=[
            SearchQuery(
                query_id=f"q{index}",
                gap_id=f"g{((index - 1) % 6) + 1}",
                query=f"protein function evidence query {index}",
            )
            for index in range(1, 13)
        ],
    )

    normalized = _normalize_plan_to_query_budget(plan, query_budget=10)

    assert len(normalized.search_queries) == 10
    assert {query.gap_id for query in normalized.search_queries} == {
        "g1",
        "g2",
        "g3",
        "g4",
        "g5",
        "g6",
    }
    assert _BUDGET_NORMALIZATION_RISK in normalized.risks
    normalized.validate_query_budget(10)


def test_plan_normalization__repository_or_dataset_query__adds_web_lane() -> None:
    from paperagent.nodes.planning import _normalize_plan_to_query_budget
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="asset discovery",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="find implementation")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="g1",
                query="GraphSAGE official implementation repository",
                source_types=["paper", "repository"],
            )
        ],
    )

    normalized = _normalize_plan_to_query_budget(plan, query_budget=10)

    assert normalized.search_queries[0].source_types == [
        "paper",
        "repository",
        "dataset",
        "web",
    ]


def test_user_material_identity_queries_add_exact_paper_and_repository_lanes() -> None:
    from paperagent.nodes.planning import _ensure_user_material_identity_queries
    from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="verify supplied baseline",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="baseline evidence")],
        search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="task evidence")],
    )
    request = ResearchRequest(
        question="verify supplied baseline",
        user_material_refs=["A Concrete Method [declared role: baseline]"],
    )

    updated = _ensure_user_material_identity_queries(plan, request, query_budget=10)
    identity_gap_ids = {
        gap.gap_id for gap in updated.evidence_gaps if gap.gap_id.startswith("user-material")
    }
    identity_queries = [
        query for query in updated.search_queries if query.gap_id in identity_gap_ids
    ]

    assert [query.query for query in identity_queries] == [
        '"A Concrete Method"',
        '"A Concrete Method" official implementation code repository',
    ]
    assert identity_queries[0].source_types == ["paper", "web"]
    assert identity_queries[1].source_types == ["repository", "web"]


def test_plan_normalization__baseline_query_adds_asset_lanes_without_extra_query() -> None:
    from paperagent.nodes.planning import _normalize_plan_to_query_budget
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="few-shot scientific classification",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="baseline", description="find a baseline")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="baseline",
                query="reproducible classification baseline",
                source_types=["paper"],
            )
        ],
    )

    normalized = _normalize_plan_to_query_budget(plan, query_budget=10)

    assert len(normalized.search_queries) == 1
    assert normalized.search_queries[0].source_types == [
        "paper",
        "repository",
        "dataset",
        "web",
    ]


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


def test_baseline_query_completion_does_not_add_gap_without_role_contract() -> None:
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


def test_baseline_query_completion_records_budget_risk_without_eviction() -> None:
    from paperagent.nodes.planning import (
        _BASELINE_QUERY_ABSENT_RISK,
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
    assert _BASELINE_QUERY_ABSENT_RISK in updated.risks


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


def test_comparator_only_gap_does_not_become_development_baseline_query() -> None:
    from paperagent.nodes.planning import (
        _BASELINE_QUERY_ABSENT_RISK,
        _ensure_baseline_role_query,
    )
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    query = SearchQuery(
        query_id="q-comparator",
        gap_id="strong-comparator",
        query="strong comparator comparison under matched compute",
        source_types=["paper"],
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="task",
        scope="test",
        evidence_gaps=[
            EvidenceGap(gap_id="strong-comparator", description="strong comparison evidence")
        ],
        search_queries=[query],
    )
    updated = _ensure_baseline_role_query(plan, query_budget=10)
    assert updated.search_queries == [query]
    assert _BASELINE_QUERY_ABSENT_RISK in updated.risks
