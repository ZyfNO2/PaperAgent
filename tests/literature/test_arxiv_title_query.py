from __future__ import annotations

import asyncio

from paperagent.literature.providers.arxiv import ArxivProvider
from paperagent.literature.providers.base import HTTPResponse
from paperagent.schemas.literature import LiteratureFilters, QueryLane


class _CapturingTransport:
    def __init__(self) -> None:
        self.params: dict[str, str | int] | None = None

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        del url, headers, timeout
        self.params = params
        return HTTPResponse(
            status_code=200,
            headers={},
            json_data=None,
            text=(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
            ),
        )


def test_baseline_identity_uses_arxiv_title_field_query() -> None:
    transport = _CapturingTransport()
    provider = ArxivProvider(transport=transport)
    lane = QueryLane(
        lane_id="identity",
        purpose="baseline",
        query="USAD: UnSupervised Anomaly Detection on Multivariate Time Series",
        source_preferences=["arxiv"],
        gap_ids=["g1"],
        priority=95,
    )
    asyncio.run(provider.search(lane=lane, filters=LiteratureFilters(), limit=5))
    assert transport.params is not None
    assert transport.params["search_query"] == (
        'ti:"USAD: UnSupervised Anomaly Detection on Multivariate Time Series"'
    )


def test_non_identity_arxiv_query_remains_full_text() -> None:
    transport = _CapturingTransport()
    provider = ArxivProvider(transport=transport)
    lane = QueryLane(
        lane_id="dataset-relation",
        purpose="benchmark_dataset",
        query='"MIMII" dataset benchmark baseline method comparison',
        source_preferences=["arxiv"],
        gap_ids=["g1"],
        priority=75,
    )
    asyncio.run(provider.search(lane=lane, filters=LiteratureFilters(), limit=5))
    assert transport.params is not None
    assert transport.params["search_query"] == (
        'all:"MIMII" dataset benchmark baseline method comparison'
    )
