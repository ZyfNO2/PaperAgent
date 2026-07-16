from __future__ import annotations

import os

import pytest

from paperagent.literature.factory import (
    LiteratureProviderSettings,
    build_literature_runtime,
)
from paperagent.literature.providers import ArxivProvider, OpenAlexProvider
from paperagent.literature.verification import CrossrefVerifier
from paperagent.schemas.literature import LiteratureFilters, PaperRecord, QueryLane

pytestmark = [pytest.mark.real_provider, pytest.mark.network]

RUN_REAL = os.getenv("PAPERAGENT_RUN_REAL_PROVIDER") == "1"


def _settings() -> LiteratureProviderSettings:
    return LiteratureProviderSettings(
        contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL") or None,
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None,
        provider_timeout_seconds=20,
        round_deadline_seconds=45,
    )


@pytest.mark.skipif(not RUN_REAL, reason="set PAPERAGENT_RUN_REAL_PROVIDER=1")
@pytest.mark.asyncio
async def test_openalex_arxiv_and_crossref_real_smoke() -> None:
    runtime = build_literature_runtime(_settings())
    try:
        lane = QueryLane(
            lane_id="smoke",
            purpose="baseline",
            query="attention is all you need",
            source_preferences=["openalex", "arxiv"],
            gap_ids=["existence"],
        )
        filters = LiteratureFilters(year_min=2017, year_max=2026)
        openalex = OpenAlexProvider(
            transport=runtime.transport,
            mailto=_settings().contact_email,
            timeout_seconds=20,
        )
        arxiv = ArxivProvider(transport=runtime.transport, timeout_seconds=20)
        openalex_result = await openalex.search(lane=lane, filters=filters, limit=3)
        arxiv_result = await arxiv.search(lane=lane, filters=filters, limit=3)
        assert openalex_result.status == "success"
        assert arxiv_result.status == "success"

        attempt = await CrossrefVerifier(
            transport=runtime.transport,
            timeout_seconds=20,
            mailto=_settings().contact_email,
        ).verify(
            PaperRecord(
                paper_id="smoke-deep-learning",
                canonical_title="Deep learning",
                doi="10.1038/nature14539",
            )
        )
        assert attempt.status == "verified"
        assert attempt.method == "crossref_doi_exact"
    finally:
        await runtime.aclose()
