from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.literature.planner import plan_literature_queries
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.literature.verification import VerificationService
from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery
from paperagent.schemas.literature import ProviderPaper, ProviderResult

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeProvider:
    provider_name = "openalex"
    contract_version = "test-v1"

    def __init__(self, provider_name: str, results: list[ProviderResult]) -> None:
        self.provider_name = provider_name
        self.results = results
        self.calls = 0

    async def search(self, *, lane, filters, limit):
        del filters
        self.calls += 1
        result = self.results[min(self.calls - 1, len(self.results) - 1)]
        papers = [
            paper.model_copy(
                update={
                    "matched_gap_ids": list(lane.gap_ids),
                    "source_lane_ids": [lane.lane_id],
                }
            )
            for paper in result.papers[:limit]
        ]
        return result.model_copy(update={"papers": papers})


def provider_result(
    provider: str, status: str, papers: list[ProviderPaper] | None = None
) -> ProviderResult:
    kwargs: dict[str, str] = {}
    if status in {"failed", "timeout", "rate_limited"}:
        kwargs = {"error_code": status.upper(), "error_message": status}
    return ProviderResult(
        provider=provider,
        request_id=f"req-{provider}-{status}",
        status=status,
        papers=papers or [],
        started_at=NOW,
        finished_at=NOW,
        **kwargs,
    )


def research_plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="Evaluate retrieval",
        scope="IR",
        research_questions=["What works?"],
        evidence_gaps=[
            EvidenceGap(gap_id="method", description="method evidence"),
            EvidenceGap(gap_id="failure", description="failure evidence"),
        ],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="method",
                query="retrieval method benchmark",
                source_types=["paper"],
            ),
            SearchQuery(
                query_id="q2",
                gap_id="failure",
                query="retrieval limitations failures",
                source_types=["paper"],
            ),
        ],
        success_criteria=["coverage"],
        risks=[],
    )


def test_existing_research_plan_maps_to_v02_query_lanes() -> None:
    plan = plan_literature_queries(research_plan(), question="How reliable is retrieval?")
    assert plan.schema_version == "0.2"
    assert plan.required_gap_ids == ["method", "failure"]
    assert [lane.purpose for lane in plan.query_lanes] == ["method", "limitation_failure"]
    assert all(len(lane.source_preferences) == 2 for lane in plan.query_lanes)


@pytest.mark.asyncio
async def test_adapter_returns_verified_candidate_metadata_and_stable_id() -> None:
    raw = ProviderPaper(
        provider_record_id="p1",
        title="Reliable Retrieval",
        authors=["Jane Doe"],
        year=2024,
        arxiv_id="2401.12345",
        urls=["https://arxiv.org/abs/2401.12345"],
    )
    provider = FakeProvider("openalex", [provider_result("openalex", "success", [raw])])
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
    )
    adapter = LiteratureSearchAdapter(service=service, source_preferences=["openalex"])
    candidates = await adapter.search(
        query=SearchQuery(query_id="q1", gap_id="method", query="retrieval method"),
        scenario="ignored",
        call_index=0,
        fixture_version="v0.2",
        limit=10,
    )
    assert len(candidates) == 1
    assert candidates[0].candidate_id.startswith("paper-")
    assert candidates[0].metadata["verification_status"] == "verified"
    assert candidates[0].metadata["providers"] == "openalex"


@pytest.mark.asyncio
async def test_adapter_all_provider_failures_raise_provider_error() -> None:
    from paperagent.errors import ProviderError

    service = LiteratureRetrievalService(
        providers=[FakeProvider("openalex", [provider_result("openalex", "failed")])],
        verifier=VerificationService([]),
    )
    adapter = LiteratureSearchAdapter(service=service, source_preferences=["openalex"])
    with pytest.raises(ProviderError, match="all literature providers failed"):
        await adapter.search(
            query=SearchQuery(query_id="q1", gap_id="method", query="retrieval method"),
            scenario="ignored",
            call_index=0,
            fixture_version="v0.2",
            limit=10,
        )


@pytest.mark.asyncio
async def test_verify_evidence_preserves_multi_gap_support_and_pending_status(fixed_time) -> None:
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
    candidates = [
        SearchCandidate(
            candidate_id="paper-1",
            query_id="q1",
            gap_id="method",
            source_type="paper",
            title="Paper",
            locator="https://example.test/paper",
            snippet="summary",
            provider="literature_retrieval",
            metadata={"verification_status": "pending"},
        ),
        SearchCandidate(
            candidate_id="paper-1",
            query_id="q2",
            gap_id="failure",
            source_type="paper",
            title="Paper",
            locator="https://example.test/paper",
            snippet="summary",
            provider="literature_retrieval",
            metadata={"verification_status": "pending"},
        ),
    ]
    patch = await verify_evidence_node(
        {"retrieval": RetrievalState(round=1, raw_candidates=candidates)},
        {"configurable": {"services": services}},
    )
    item = patch["evidence"].items[0]
    assert item.verification_status == "pending"
    assert item.supports_gap_ids == ["failure", "method"]
    assert patch["evidence"].coverage_by_gap == {}


@pytest.mark.asyncio
async def test_search_tool_records_partial_provider_failure_without_dropping_success(
    fixed_time,
) -> None:
    from paperagent.literature.adapter import LiteratureSearchAdapter
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider
    from paperagent.retrieval.search_tool import search_tool_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import PreparedQuery, RetrievalState, RunBudgets, RunContext
    from paperagent.testing import FixedClock, SequenceIdFactory

    raw = ProviderPaper(
        provider_record_id="p1",
        title="Reliable Retrieval",
        authors=["Jane Doe"],
        year=2024,
        arxiv_id="2401.12345",
    )
    adapter = LiteratureSearchAdapter(
        service=LiteratureRetrievalService(
            providers=[
                FakeProvider("openalex", [provider_result("openalex", "success", [raw])]),
                FakeProvider("arxiv", [provider_result("arxiv", "timeout")]),
            ],
            verifier=VerificationService([]),
        ),
        source_preferences=["openalex", "arxiv"],
    )
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        adapter,
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    state = {
        "run": RunContext(
            run_id="run",
            thread_id="thread",
            created_at=fixed_time,
            model_profile="fake",
            network_policy="allow_search",
            budgets=RunBudgets(),
        ),
        "retrieval": RetrievalState(
            round=1,
            prepared_queries=[
                PreparedQuery(
                    query_id="q1",
                    gap_id="g1",
                    query="retrieval method",
                    source_types=["paper"],
                    round=1,
                )
            ],
        ),
    }
    patch = await search_tool_node(state, {"configurable": {"services": services}})
    assert len(patch["retrieval"].raw_candidates) == 1
    assert len(patch["retrieval"].tool_errors) == 1
    error = patch["retrieval"].tool_errors[0]
    assert error.provider == "arxiv"
    assert error.code == "TIMEOUT"
    assert error.retryable is True
