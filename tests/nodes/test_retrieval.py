from __future__ import annotations

import pytest


def _plan():
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    return ResearchPlan(
        status="ready",
        problem_statement="p",
        scope="s",
        research_questions=["q"],
        evidence_gaps=[EvidenceGap(gap_id="g1", description="d", minimum_accepted_items=1)],
        search_queries=[
            SearchQuery(query_id="q1", gap_id="g1", query="first", source_types=["web"]),
            SearchQuery(query_id="q2", gap_id="g1", query="second", source_types=["web"]),
        ],
        success_criteria=["c"],
        risks=[],
    )


@pytest.mark.asyncio
async def test_prepare_search_node__budget_one__prepares_one_query_and_increments_round(
    fixed_time,
) -> None:
    from paperagent.nodes.intake import intake_node
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.prepare_search import prepare_search_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, RunBudgets
    from paperagent.state import apply_state_patch
    from paperagent.testing import FixedClock, SequenceIdFactory

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    state = {"request": ResearchRequest(question="evaluate citations")}
    state = apply_state_patch(
        state,
        await intake_node(
            state,
            {
                "configurable": {
                    "services": services,
                    "budgets": RunBudgets(max_queries_per_round=1),
                }
            },
        ),
    )
    state["plan"] = _plan()
    patch = await prepare_search_node(state, {"configurable": {"services": services}})
    assert patch["retrieval"].round == 1
    assert [query.query_id for query in patch["retrieval"].prepared_queries] == ["q1"]


@pytest.mark.asyncio
async def test_search_and_verify__valid_fixture_candidate__becomes_accepted(fixed_time) -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, SearchFixtureKey
    from paperagent.retrieval.search_tool import search_tool_node
    from paperagent.retrieval.verify_evidence import verify_evidence_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import (
        PreparedQuery,
        RetrievalState,
        RunBudgets,
        RunContext,
        SearchCandidate,
    )
    from paperagent.testing import FixedClock, SequenceIdFactory

    candidate = SearchCandidate(
        candidate_id="c1",
        query_id="q1",
        gap_id="g1",
        source_type="web",
        title="Fixture note",
        locator="fixture://candidate/c1",
        snippet="summary",
        metadata={"license": "MIT"},
    )
    search = FakeSearchProvider(
        fixtures={SearchFixtureKey(scenario="happy_path", query_id="q1", call_index=0): [candidate]}
    )
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    state = {
        "run": RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=fixed_time,
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(),
        ),
        "retrieval": RetrievalState(
            round=1,
            prepared_queries=[
                PreparedQuery(
                    query_id="q1", gap_id="g1", query="search", source_types=["web"], round=1
                )
            ],
        ),
    }
    search_patch = await search_tool_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    state["retrieval"] = search_patch["retrieval"]
    verify_patch = await verify_evidence_node(state, {"configurable": {"services": services}})
    evidence = verify_patch["evidence"]
    assert evidence.accepted_ids == ["ev-c1"]
    assert evidence.coverage_by_gap == {"g1": 1}


def test_retrieval_gate__coverage_and_round__is_bounded() -> None:
    from paperagent.retrieval.gate import retrieval_gate
    from paperagent.schemas import EvidenceBundle, RetrievalState

    assert (
        retrieval_gate(
            {"plan": _plan(), "retrieval": RetrievalState(round=1), "evidence": EvidenceBundle()}
        )
        == "retry_under_budget"
    )
    assert (
        retrieval_gate(
            {"plan": _plan(), "retrieval": RetrievalState(round=2), "evidence": EvidenceBundle()}
        )
        == "budget_exhausted"
    )


@pytest.mark.asyncio
async def test_verify_evidence__untrusted_https_without_verifier__remains_pending(
    fixed_time,
) -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.verify_evidence import verify_evidence_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import RetrievalState, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    candidate = SearchCandidate(
        candidate_id="untrusted-url",
        query_id="q1",
        gap_id="g1",
        source_type="web",
        title="Plausible but unverified URL",
        locator="https://example.invalid/hallucinated-paper",
        snippet="No verifier confirmed this result.",
        provider="generic_web_search",
    )
    patch = await verify_evidence_node(
        {"retrieval": RetrievalState(round=1, raw_candidates=[candidate])},
        {"configurable": {"services": services}},
    )

    assert patch["evidence"].accepted_ids == []
    assert patch["evidence"].pending_ids == ["ev-untrusted-url"]


@pytest.mark.asyncio
async def test_verify_evidence__explicit_rejection_overrides_prior_acceptance(
    fixed_time,
) -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.verify_evidence import verify_evidence_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import EvidenceBundle, EvidenceItem, RetrievalState, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    existing_item = EvidenceItem(
        evidence_id="ev-c1",
        source_type="paper",
        title="Previously accepted paper",
        locator="doi:10.1000/example",
        retrieved_at=fixed_time,
        verification_status="accepted",
        supports_gap_ids=["g1"],
        summary="Earlier positive result.",
        content_hash="sha256:old",
        provider="literature_retrieval",
        metadata={"verification_status": "verified", "doi": "10.1000/example"},
    )
    existing = EvidenceBundle(
        items=[existing_item],
        accepted_ids=["ev-c1"],
        coverage_by_gap={"g1": 1},
    )
    rejected = SearchCandidate(
        candidate_id="c1",
        query_id="q2",
        gap_id="g1",
        source_type="paper",
        title="Previously accepted paper",
        locator="doi:10.1000/example",
        snippet="Verifier rejected the identifier.",
        provider="literature_retrieval",
        metadata={"verification_status": "rejected", "doi": "10.1000/example"},
    )
    patch = await verify_evidence_node(
        {
            "retrieval": RetrievalState(round=2, raw_candidates=[rejected]),
            "evidence": existing,
        },
        {"configurable": {"services": services}},
    )

    assert patch["evidence"].accepted_ids == []
    assert patch["evidence"].rejected_ids == ["ev-c1"]
    assert patch["evidence"].coverage_by_gap == {}


@pytest.mark.asyncio
async def test_verify_evidence__content_hash_ignores_query_and_rank_metadata(
    fixed_time,
) -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.verify_evidence import verify_evidence_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import RetrievalState, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    first = SearchCandidate(
        candidate_id="stable-paper",
        query_id="q1",
        gap_id="g1",
        source_type="paper",
        title="Stable paper",
        locator="doi:10.1000/stable",
        snippet="Stable abstract.",
        provider="literature_retrieval",
        metadata={
            "verification_status": "verified",
            "doi": "10.1000/stable",
            "rank_score": "0.9",
            "fallback_used": "false",
        },
    )
    first_patch = await verify_evidence_node(
        {"retrieval": RetrievalState(round=1, raw_candidates=[first])},
        {"configurable": {"services": services}},
    )
    first_hash = first_patch["evidence"].items[0].content_hash

    second = first.model_copy(
        update={
            "query_id": "q2",
            "gap_id": "g2",
            "metadata": {
                **first.metadata,
                "rank_score": "0.1",
                "fallback_used": "true",
            },
        }
    )
    second_patch = await verify_evidence_node(
        {
            "retrieval": RetrievalState(round=2, raw_candidates=[second]),
            "evidence": first_patch["evidence"],
        },
        {"configurable": {"services": services}},
    )

    assert second_patch["evidence"].items[0].content_hash == first_hash
    assert second_patch["evidence"].items[0].supports_gap_ids == ["g1", "g2"]


@pytest.mark.asyncio
async def test_verify_evidence__same_id_with_different_content_is_rejected_as_conflict(
    fixed_time,
) -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.verify_evidence import verify_evidence_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import RetrievalState, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    first = SearchCandidate(
        candidate_id="collision",
        query_id="q1",
        gap_id="g1",
        source_type="paper",
        title="Stable title",
        locator="doi:10.1000/collision",
        snippet="Original abstract.",
        provider="literature_retrieval",
        metadata={"verification_status": "verified", "doi": "10.1000/collision"},
    )
    first_patch = await verify_evidence_node(
        {"retrieval": RetrievalState(round=1, raw_candidates=[first])},
        {"configurable": {"services": services}},
    )
    changed = first.model_copy(
        update={
            "query_id": "q2",
            "gap_id": "g2",
            "snippet": "Different content under the same identifier.",
        }
    )
    second_patch = await verify_evidence_node(
        {
            "retrieval": RetrievalState(round=2, raw_candidates=[changed]),
            "evidence": first_patch["evidence"],
        },
        {"configurable": {"services": services}},
    )

    assert second_patch["evidence"].accepted_ids == []
    assert second_patch["evidence"].rejected_ids == ["ev-collision"]
    assert [item.conflict_id for item in second_patch["evidence"].conflicts] == [
        "identity-ev-collision"
    ]
