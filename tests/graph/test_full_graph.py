from __future__ import annotations

import pytest

from conftest import load_llm_raw


def _services(fixed_time, *, planning="happy_path", method="happy_path"):
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    fixtures = {
        FixtureKey(task="planning", scenario=planning, call_index=0): load_llm_raw(
            "planning", planning, 0
        ),
        FixtureKey(task="evidence_synthesis", scenario="happy_path", call_index=0): load_llm_raw(
            "evidence_synthesis", "happy_path", 0
        ),
        FixtureKey(task="method_design", scenario=method, call_index=0): load_llm_raw(
            "method_design", method, 0
        ),
        FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
            "report", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }
    if method == "gate_repair_method":
        fixtures[FixtureKey(task="method_design", scenario=method, call_index=1)] = load_llm_raw(
            "method_design", method, 1
        )
    candidates = {
        SearchFixtureKey(scenario="happy_path", query_id="query-support-01", call_index=0): [
            SearchCandidate(
                candidate_id="support-001",
                query_id="query-support-01",
                gap_id="gap-support",
                source_type="user_material",
                title="Synthetic support note",
                locator="fixture://evidence/ev-support-001",
                snippet="Claim support can be measured.",
                metadata={"license": "MIT"},
            )
        ],
        SearchFixtureKey(scenario="happy_path", query_id="query-ablation-01", call_index=0): [
            SearchCandidate(
                candidate_id="ablation-001",
                query_id="query-ablation-01",
                gap_id="gap-ablation",
                source_type="user_material",
                title="Synthetic ablation note",
                locator="fixture://evidence/ev-ablation-001",
                snippet="Context ablation separates errors.",
                metadata={"license": "MIT"},
            )
        ],
    }
    return RuntimeServices(
        FakeLLMProvider(fixtures=fixtures),
        FakeSearchProvider(fixtures=candidates),
        FixedClock(fixed_time),
        SequenceIdFactory("graph"),
        InMemoryStateStore(),
    )


@pytest.mark.asyncio
async def test_graph__happy_path__runs_compiled_langgraph_with_four_llm_calls(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.schemas import ResearchRequest

    services = _services(fixed_time)
    graph = build_graph()
    result = await graph.ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {"configurable": {"services": services, "scenario": "happy_path"}},
    )
    assert result["execution"].status == "completed"
    assert result["quality"].verdict == "pass"
    assert result["report"].status == "completed"
    assert len(services.llm.calls) == 4
    assert len(services.search.calls) == 2
    completed_nodes = [
        event.node for event in result["trace"] if event.event_type == "node.completed"
    ]
    assert completed_nodes == [
        "intake_node",
        "planning_node",
        "prepare_search_node",
        "search_tool_node",
        "verify_evidence_node",
        "evidence_synthesis_node",
        "method_design_node",
        "methodology_audit_node",
        "quality_gate_node",
        "report_node",
        "persist_node",
    ]


@pytest.mark.asyncio
async def test_graph__planning_blocked__routes_directly_to_blocked_report(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.schemas import ResearchRequest

    services = _services(fixed_time, planning="blocked")
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Prove a result without evidence")},
        {"configurable": {"services": services, "scenarios": {"planning": "blocked"}}},
    )
    assert result["report"].status == "blocked"
    assert result["execution"].status == "blocked"
    assert len(services.llm.calls) == 2
    assert services.search.calls == []


@pytest.mark.asyncio
async def test_graph__method_repair__runs_exactly_one_repair(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.schemas import ResearchRequest

    services = _services(fixed_time, method="gate_repair_method")
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {
            "configurable": {
                "services": services,
                "scenarios": {
                    "planning": "happy_path",
                    "evidence_synthesis": "happy_path",
                    "method_design": "gate_repair_method",
                    "report": "happy_path",
                },
                "search_scenario": "happy_path",
            }
        },
    )
    assert result["quality"].verdict == "pass"
    assert result["execution"].repair_count == 1
    method_calls = [call for call in services.llm.calls if call.key.task == "method_design"]
    assert [call.key.call_index for call in method_calls] == [0, 1]


@pytest.mark.asyncio
async def test_graph__retrieval_retry__succeeds_on_second_round(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.schemas import ResearchRequest, RunBudgets

    services = _services(fixed_time)
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {
            "configurable": {
                "services": services,
                "scenario": "happy_path",
                "budgets": RunBudgets(max_queries_per_round=1),
            }
        },
    )
    assert result["execution"].status == "completed"
    assert result["retrieval"].round == 2
    assert len(services.search.calls) == 2
    prepare_completions = [
        event
        for event in result["trace"]
        if event.node == "prepare_search_node" and event.event_type == "node.completed"
    ]
    assert len(prepare_completions) == 2


@pytest.mark.asyncio
async def test_graph__planning_provider_timeout__produces_typed_blocked_report(
    fixed_time,
) -> None:
    from paperagent.errors import ProviderTimeoutError
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest
    from paperagent.testing import FixedClock, SequenceIdFactory

    planning_key = FixtureKey(task="planning", scenario="timeout", call_index=0)
    llm = FakeLLMProvider(
        fixtures={
            planning_key: load_llm_raw("planning", "happy_path", 0),
            FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
                "report", "blocked", 0
            ),
        },
        failures={planning_key: ProviderTimeoutError(provider="fake_llm", task="planning")},
    )
    services = RuntimeServices(
        llm,
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("timeout"),
        InMemoryStateStore(),
    )
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate a system")},
        {"configurable": {"services": services, "scenarios": {"planning": "timeout"}}},
    )
    assert result["execution"].status == "blocked"
    assert result["execution"].last_error.code == "PROVIDER_TIMEOUT"
    assert result["report"].status == "blocked"
    assert any(event.event_type == "llm.failed" for event in result["trace"])


@pytest.mark.asyncio
async def test_graph__malformed_planning_json__does_not_fallback(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest
    from paperagent.testing import FixedClock, SequenceIdFactory

    llm = FakeLLMProvider(
        fixtures={
            FixtureKey(task="planning", scenario="malformed", call_index=0): '{"status":',
            FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
                "report", "blocked", 0
            ),
        }
    )
    services = RuntimeServices(
        llm,
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("malformed"),
        InMemoryStateStore(),
    )
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate a system")},
        {
            "configurable": {
                "services": services,
                "scenarios": {"planning": "malformed"},
            }
        },
    )
    assert result["execution"].last_error.code == "LLM_RESPONSE_JSON_INVALID"
    assert result["report"].status == "blocked"
    assert result.get("plan") is None


@pytest.mark.asyncio
async def test_graph__failed_synthesis__short_circuits_method_and_reports_blocked(
    fixed_time,
) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    llm = FakeLLMProvider(
        fixtures={
            FixtureKey(task="planning", scenario="synthesis_failure", call_index=0): load_llm_raw(
                "planning", "happy_path", 0
            ),
            FixtureKey(
                task="evidence_synthesis", scenario="synthesis_failure", call_index=0
            ): '{"verified_findings":',
            FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
                "report", "blocked", 0
            ),
        }
    )
    search = FakeSearchProvider(
        fixtures={
            SearchFixtureKey(scenario="synthesis_failure", query_id=query_id, call_index=0): [
                SearchCandidate(
                    candidate_id=candidate_id,
                    query_id=query_id,
                    gap_id=gap_id,
                    source_type="paper",
                    title="Verified source",
                    locator=f"doi:10.1000/{candidate_id}",
                    snippet="Verified evidence",
                )
            ]
            for query_id, candidate_id, gap_id in (
                ("query-support-01", "support-001", "gap-support"),
                ("query-ablation-01", "ablation-001", "gap-ablation"),
            )
        }
    )
    services = RuntimeServices(
        llm,
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("synthesis-failure"),
        InMemoryStateStore(),
    )

    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {
            "configurable": {
                "services": services,
                "scenarios": {
                    "planning": "synthesis_failure",
                    "evidence_synthesis": "synthesis_failure",
                    "report": "blocked",
                },
                "search_scenario": "synthesis_failure",
            }
        },
    )

    assert result["execution"].status == "blocked"
    assert result["execution"].last_error.code == "LLM_RESPONSE_JSON_INVALID"
    assert result["report"].status == "blocked"
    assert result.get("synthesis") is None
    assert result.get("method") is None
    assert all(call.key.task != "method_design" for call in llm.calls)


@pytest.mark.asyncio
async def test_graph__quality_repair_retrieval__uses_remaining_round_then_passes(
    fixed_time,
) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, RunBudgets, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    scenario = "repair_retrieval"
    llm_fixtures = {}
    for task, calls in {
        "planning": 1,
        "evidence_synthesis": 2,
        "method_design": 2,
        "report": 1,
    }.items():
        for call_index in range(calls):
            llm_fixtures[FixtureKey(task=task, scenario=scenario, call_index=call_index)] = (
                load_llm_raw(task, scenario, call_index)
            )
    search = FakeSearchProvider(
        fixtures={
            SearchFixtureKey(scenario=scenario, query_id="query-support-01", call_index=0): [
                SearchCandidate(
                    candidate_id="support-001",
                    query_id="query-support-01",
                    gap_id="gap-support",
                    source_type="user_material",
                    title="Support note",
                    locator="fixture://support",
                    snippet="support",
                    metadata={"license": "MIT"},
                )
            ],
            SearchFixtureKey(scenario=scenario, query_id="query-ablation-01", call_index=0): [
                SearchCandidate(
                    candidate_id="ablation-001",
                    query_id="query-ablation-01",
                    gap_id="gap-ablation",
                    source_type="user_material",
                    title="Ablation note",
                    locator="fixture://ablation",
                    snippet="ablation",
                    metadata={"license": "MIT"},
                )
            ],
            SearchFixtureKey(scenario=scenario, query_id="query-extra-01", call_index=0): [
                SearchCandidate(
                    candidate_id="extra-001",
                    query_id="query-extra-01",
                    gap_id="gap-support",
                    source_type="user_material",
                    title="Additional support note",
                    locator="fixture://extra",
                    snippet="additional support",
                    metadata={"license": "MIT"},
                )
            ],
        }
    )
    services = RuntimeServices(
        FakeLLMProvider(fixtures=llm_fixtures),
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("repair-retrieval"),
        InMemoryStateStore(),
    )
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {
            "configurable": {
                "services": services,
                "scenario": scenario,
                "budgets": RunBudgets(max_queries_per_round=2),
            }
        },
    )
    assert result["execution"].status == "completed"
    assert result["quality"].verdict == "pass"
    assert result["retrieval"].round == 2
    assert [call.key.query_id for call in search.calls] == [
        "query-support-01",
        "query-ablation-01",
        "query-extra-01",
    ]
    routes = [event.route for event in result["trace"] if event.event_type == "route.decided"]
    assert "repair_retrieval" in routes
