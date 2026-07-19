from __future__ import annotations

import pytest

from paperagent.literature.providers.base import response_success, utc_now
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.literature.verification import VerificationService
from paperagent.schemas.literature import LiteratureQueryPlan, ProviderResult, QueryLane


class EmptyProvider:
    provider_name = "openalex"
    contract_version = "test"

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, **_: object) -> ProviderResult:
        self.calls += 1
        return response_success(
            provider=self.provider_name,
            request_id=f"req-{self.calls}",
            started_at=utc_now(),
            papers=[],
        )


class CountingRewriter:
    def __init__(self) -> None:
        self.calls = 0

    async def rewrite(self, *_: object) -> list[QueryLane]:
        self.calls += 1
        return []


def _plan(query: str, lane_id: str) -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question=query,
        scope="test",
        query_lanes=[
            QueryLane(
                lane_id=lane_id,
                purpose="method",
                query=query,
                source_preferences=["openalex"],
                gap_ids=["gap-1"],
            )
        ],
        required_gap_ids=["gap-1"],
        max_rounds=1,
    )


@pytest.mark.asyncio
async def test_single_round_plan_does_not_trigger_hidden_query_rewrite() -> None:
    provider = EmptyProvider()
    rewriter = CountingRewriter()
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        cache=None,
        rewriter=rewriter,
        max_provider_calls=4,
    )

    bundle = await service.retrieve(_plan("specific UAV detector benchmark", "lane-1"))

    assert provider.calls == 1
    assert rewriter.calls == 0
    assert bundle.metrics.rounds == 1
    assert bundle.metrics.query_rewrite_calls == 0


@pytest.mark.asyncio
async def test_task_provider_budget_blocks_extra_external_calls() -> None:
    provider = EmptyProvider()
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        cache=None,
        max_provider_calls=1,
    )

    first = await service.retrieve(_plan("specific UAV detector benchmark", "lane-1"))
    second = await service.retrieve(_plan("specific crack segmentation benchmark", "lane-2"))

    assert first.provider_results[0].status == "empty"
    assert second.provider_results[0].status == "failed"
    assert second.provider_results[0].error_code == "PROVIDER_CALL_BUDGET_EXHAUSTED"
    assert provider.calls == 1
    assert service.provider_call_budget() == {"maximum": 1, "used": 1, "remaining": 0}
