from __future__ import annotations

from typing import Any, cast

import pytest

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.prompts import get_prompt
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import (
    CoverageReport,
    LiteratureBundle,
    PaperRecord,
    RetrievalMetrics,
)


class _FallbackService:
    def __init__(self) -> None:
        self.plans = []

    async def retrieve(self, plan):
        self.plans.append(plan)
        if len(self.plans) == 1:
            return LiteratureBundle(
                papers=[],
                coverage=CoverageReport(),
                metrics=RetrievalMetrics(),
            )
        return LiteratureBundle(
            papers=[
                PaperRecord(
                    paper_id="arxiv:2302.12173",
                    canonical_title="Indirect prompt injection",
                    arxiv_id="2302.12173",
                    verification_status="verified",
                )
            ],
            coverage=CoverageReport(),
            metrics=RetrievalMetrics(),
        )


def test_planning_prompt_v012_is_budget_aware_and_fail_closed() -> None:
    prompt = get_prompt("planning")

    assert prompt.version == "planning.v0.1.2"
    assert "2-4 scientifically indispensable gaps" in prompt.system
    assert "Keep minimum_accepted_items at 1" in prompt.system
    assert "cannot exist in public search" in prompt.system
    assert "return blocked" in prompt.system
    assert "Never fabricate" in prompt.system


@pytest.mark.asyncio
async def test_arxiv_fallback_is_used_only_after_zero_verified_primary_results() -> None:
    service = _FallbackService()
    adapter = LiteratureSearchAdapter(
        service=cast(Any, service),
        source_preferences=["openalex", "semantic_scholar"],
        fallback_source_preferences=["arxiv", "openalex"],
    )
    query = SearchQuery(
        query_id="q1",
        gap_id="g1",
        query="indirect prompt injection literature agents",
        source_types=["paper"],
    )

    candidates = await adapter.search(
        query=query,
        scenario="live",
        call_index=0,
        fixture_version="v1",
        limit=10,
    )

    assert len(service.plans) == 2
    assert service.plans[0].query_lanes[0].source_preferences == [
        "openalex",
        "semantic_scholar",
    ]
    assert service.plans[1].query_lanes[0].source_preferences == ["arxiv", "openalex"]
    assert len(candidates) == 1
    assert candidates[0].metadata["fallback_used"] == "true"
    diagnostics = adapter.last_query_diagnostics("q1")
    assert diagnostics["fallback_used"] is True
