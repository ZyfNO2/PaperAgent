from __future__ import annotations

import json
from datetime import datetime

import pytest

from conftest import load_llm_raw

NORMAL_CASES = [
    ("ood_cv", "industrial defect detection"),
    ("ood_nlp", "dialect text classification"),
    ("ood_recsys", "cold-start recommendation"),
    ("ood_timeseries", "sensor anomaly detection"),
    ("ood_database", "database index strategy"),
    ("ood_software", "API migration regression"),
]
FORBIDDEN = [
    "citation reliability",
    "claim support rate",
    "Nobel Prize in Physics 2024",
    "ResearchState",
    "Re8",
]


def _services(fixed_time: datetime, scenario: str):
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
        FixtureKey(task=task, scenario=scenario, call_index=0): load_llm_raw(task, scenario, 0)
        for task in ("planning", "evidence_synthesis", "method_design", "report")
    }
    search = FakeSearchProvider(
        fixtures={
            SearchFixtureKey(scenario=scenario, query_id="query-evidence-01", call_index=0): [
                SearchCandidate(
                    candidate_id="evidence-001",
                    query_id="query-evidence-01",
                    gap_id="gap-evidence",
                    source_type="user_material",
                    title="Synthetic domain evidence",
                    locator="fixture://ood/evidence",
                    snippet="Synthetic evidence for workflow verification.",
                    metadata={
                        "license": "MIT",
                        "baseline_reproduced": "true",
                        "baseline_reproduced_metric": "primary_metric=0.50",
                        "baseline_compute_fit": "true",
                        "baseline_parity_verified": "true",
                        "dataset_fingerprint": "sha256:fixture-dataset",
                        "environment_fingerprint": "sha256:fixture-environment",
                        "relevance_scope": "direct",
                        "supporting_spans": "Synthetic domain evidence fixture.",
                        "fixture_gap_support_ids": "gap-evidence",
                    },
                )
            ],
            SearchFixtureKey(scenario=scenario, query_id="query-evaluation-01", call_index=0): [
                SearchCandidate(
                    candidate_id="evaluation-001",
                    query_id="query-evaluation-01",
                    gap_id="gap-evaluation",
                    source_type="user_material",
                    title="Synthetic evaluation evidence",
                    locator="fixture://ood/evaluation",
                    snippet="Synthetic evaluation contract.",
                    metadata={
                        "license": "MIT",
                        "relevance_scope": "direct",
                        "supporting_spans": "Synthetic evaluation evidence fixture.",
                        "fixture_gap_support_ids": "gap-evaluation",
                    },
                )
            ],
        }
    )
    return RuntimeServices(
        FakeLLMProvider(fixtures=fixtures),
        search,
        FixedClock(fixed_time),
        SequenceIdFactory(scenario),
        InMemoryStateStore(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("scenario", "domain_marker"), NORMAL_CASES)
async def test_ood_graph__domain_case__terminates_without_cross_domain_leakage(
    fixed_time: datetime, scenario: str, domain_marker: str
) -> None:
    from paperagent.graph import build_graph
    from paperagent.schemas import ResearchRequest
    from paperagent.state import state_to_primitive

    services = _services(fixed_time, scenario)
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question=f"Evaluate {domain_marker}")},
        {
            "configurable": {
                "services": services,
                "scenarios": {
                    "planning": scenario,
                    "evidence_synthesis": scenario,
                    "method_design": scenario,
                    "report": scenario,
                },
                "search_scenario": scenario,
            }
        },
    )
    assert result["execution"].status == "completed"
    assert result["quality"].verdict == "pass"
    assert len(services.llm.calls) == 4
    assert len(services.search.calls) == 2
    text = json.dumps(state_to_primitive(result), ensure_ascii=False).lower()
    assert domain_marker.lower() in text
    for marker in FORBIDDEN:
        assert marker.lower() not in text


@pytest.mark.asyncio
async def test_ood_graph__underspecified__pauses_for_human(fixed_time: datetime) -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest
    from paperagent.testing import FixedClock, SequenceIdFactory

    scenario = "ood_underspecified"
    services = RuntimeServices(
        FakeLLMProvider(
            fixtures={
                FixtureKey(task="planning", scenario=scenario, call_index=0): load_llm_raw(
                    "planning", scenario, 0
                )
            }
        ),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory(scenario),
        InMemoryStateStore(),
    )
    result = await build_graph(checkpointer=InMemorySaver()).ainvoke(
        {"request": ResearchRequest(question="Study this")},
        {
            "configurable": {
                "thread_id": "ood-underspecified-thread",
                "services": services,
                "scenarios": {"planning": scenario},
            }
        },
    )
    assert result["__interrupt__"]
    assert len(services.llm.calls) == 1
    assert services.search.calls == []


@pytest.mark.asyncio
async def test_ood_graph__impossible_claim__blocks_without_search(fixed_time: datetime) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest
    from paperagent.testing import FixedClock, SequenceIdFactory

    scenario = "ood_impossible"
    services = RuntimeServices(
        FakeLLMProvider(
            fixtures={
                FixtureKey(task="planning", scenario=scenario, call_index=0): load_llm_raw(
                    "planning", scenario, 0
                ),
                FixtureKey(task="report", scenario=scenario, call_index=0): load_llm_raw(
                    "report", scenario, 0
                ),
            }
        ),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory(scenario),
        InMemoryStateStore(),
    )
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Prove 99% accuracy without data")},
        {
            "configurable": {
                "services": services,
                "scenarios": {"planning": scenario, "report": scenario},
            }
        },
    )
    assert result["execution"].status == "blocked"
    assert result["report"].status == "blocked"
    assert len(services.llm.calls) == 2
    assert services.search.calls == []
