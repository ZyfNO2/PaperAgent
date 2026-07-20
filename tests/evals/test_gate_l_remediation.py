from __future__ import annotations

from typing import Any, cast

import pytest

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.prompts import get_prompt
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import (
    CoverageReport,
    LiteratureBundle,
    LiteratureQueryPlan,
    PaperRecord,
    RankFeatures,
    RetrievalMetrics,
)


class _FallbackService:
    provider_names = ("openalex", "semantic_scholar", "arxiv")

    def __init__(self) -> None:
        self.plans: list[LiteratureQueryPlan] = []

    async def retrieve(self, plan: LiteratureQueryPlan) -> LiteratureBundle:
        self.plans.append(plan)
        if len(self.plans) < 3:
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
                    rank_features=RankFeatures(
                        relevance=0.8,
                        gap_coverage=1.0,
                        metadata_verification=1.0,
                        recency_fit=0.8,
                        diversity=0.5,
                        citation_tiebreaker=0.0,
                        score=0.82,
                        explanation=[],
                    ),
                )
            ],
            coverage=CoverageReport(),
            metrics=RetrievalMetrics(),
        )


def test_planning_prompt_v012_is_budget_aware_and_fail_closed() -> None:
    prompt = get_prompt("planning")

    assert prompt.version == "planning.v0.1.2"
    assert "Choose the number and boundaries of evidence gaps" in prompt.system
    assert "Keep minimum_accepted_items at 1" in prompt.system
    assert "cannot exist in public search" in prompt.system
    assert "blocked with the evidence deficiency" in prompt.system
    assert "Never fabricate" in prompt.system
    assert "exactly two consolidated required gaps" not in prompt.system
    assert "role-explicit gap descriptions" not in prompt.system


@pytest.mark.asyncio
async def test_arxiv_escalation_is_used_only_after_primary_sources_are_insufficient() -> None:
    service = _FallbackService()
    adapter = LiteratureSearchAdapter(
        service=cast(Any, service),
        source_preferences=["openalex", "semantic_scholar"],
        supplement_source_preferences=["arxiv"],
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

    assert len(service.plans) == 3
    assert [plan.query_lanes[0].source_preferences for plan in service.plans] == [
        ["openalex"],
        ["semantic_scholar"],
        ["arxiv"],
    ]
    assert len(candidates) == 1
    assert candidates[0].metadata["fallback_used"] == "false"
    diagnostics = adapter.last_query_diagnostics("q1")
    assert diagnostics["attempted_providers"] == [
        "openalex",
        "semantic_scholar",
        "arxiv",
    ]
    assert diagnostics["fallback_used"] is False
