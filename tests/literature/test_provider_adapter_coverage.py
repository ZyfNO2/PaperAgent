from __future__ import annotations

from typing import Any

import httpx
import pytest

from paperagent.literature.providers.arxiv import ArxivProvider
from paperagent.literature.providers.base import HTTPResponse
from paperagent.literature.providers.openalex import OpenAlexProvider
from paperagent.literature.providers.semantic_scholar import SemanticScholarProvider
from paperagent.schemas.literature import LiteratureFilters, ProviderPaper, QueryLane


class CaptureTransport:
    def __init__(self, response: HTTPResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 10.0,
    ) -> HTTPResponse:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.response

    async def post(
        self,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 10.0,
    ) -> HTTPResponse:
        del url, json_body, data, headers, timeout
        return self.response


def lane(*, purpose: str = "method") -> QueryLane:
    return QueryLane(
        lane_id="lane-1",
        purpose=purpose,
        query='reliable "retrieval"',
        gap_ids=["gap-1"],
    )


@pytest.mark.asyncio
async def test_openalex_key_filters_mailto_and_sparse_metadata_branches() -> None:
    transport = CaptureTransport(
        HTTPResponse(
            200,
            {},
            {
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "display_name": "Reliable Retrieval",
                        "publication_year": "unknown",
                        "abstract_inverted_index": {
                            "Reliable": [1, "bad"],
                            3: [0],
                            "ignored": "bad",
                        },
                        "authorships": [
                            "bad",
                            {"author": "bad"},
                            {"author": {"display_name": "Jane Doe"}},
                        ],
                        "primary_location": {
                            "landing_page_url": "https://example.test/paper",
                            "source": {"display_name": "Journal"},
                        },
                        "doi": "https://doi.org/10.1000/reliable",
                        "cited_by_count": 4,
                        "type": "article",
                        "language": "en",
                    }
                ]
            },
            "",
        )
    )
    provider = OpenAlexProvider(
        transport=transport,
        api_key="test-key",
        mailto="dev@example.com",
    )

    result = await provider.search(
        lane=lane(),
        filters=LiteratureFilters(year_min=2020, year_max=2026),
        limit=50,
    )

    assert result.status == "success"
    assert result.papers[0].authors == ["Jane Doe"]
    assert result.papers[0].year is None
    assert result.papers[0].abstract == "Reliable"
    params = transport.calls[0]["params"]
    assert params is not None
    assert params["per-page"] == 50
    assert params["api_key"] == "test-key"
    assert params["mailto"] == "dev@example.com"
    assert params["filter"] == "from_publication_date:2020-01-01,to_publication_date:2026-12-31"


def test_openalex_abstract_and_parse_type_guards() -> None:
    assert OpenAlexProvider._abstract(None) is None
    assert OpenAlexProvider._abstract({}) is None
    with pytest.raises(TypeError, match="must be an object"):
        OpenAlexProvider._parse_work("bad", lane())


@pytest.mark.asyncio
async def test_semantic_scholar_open_year_range_key_and_sparse_fields() -> None:
    transport = CaptureTransport(
        HTTPResponse(
            200,
            {},
            {
                "data": [
                    {
                        "paperId": "S1",
                        "title": "Reliable Retrieval",
                        "abstract": None,
                        "year": "unknown",
                        "authors": ["bad", {"name": "Jane Doe"}],
                        "externalIds": "bad",
                        "venue": None,
                        "url": None,
                        "citationCount": 0,
                        "publicationTypes": "bad",
                    }
                ]
            },
            "",
        )
    )
    provider = SemanticScholarProvider(transport=transport, api_key="s2-key")

    result = await provider.search(
        lane=lane(),
        filters=LiteratureFilters(year_min=2020),
        limit=150,
    )

    assert result.status == "success"
    assert result.papers[0].authors == ["Jane Doe"]
    assert result.papers[0].publication_type is None
    params = transport.calls[0]["params"]
    assert params is not None
    assert params["limit"] == 100
    assert params["year"] == "2020-"
    assert transport.calls[0]["headers"] == {"x-api-key": "s2-key"}


def test_semantic_scholar_parse_type_guard() -> None:
    with pytest.raises(TypeError, match="must be an object"):
        SemanticScholarProvider._parse_paper("bad", lane())


def test_arxiv_legacy_timeout_and_year_filter_branches() -> None:
    provider = ArxivProvider(
        transport=CaptureTransport(HTTPResponse(200, {}, None, "")), timeout_seconds=7
    )
    assert provider._timeout.connect == 7
    assert provider._timeout.read == 7

    unknown = ProviderPaper(provider_record_id="x", title="Unknown", year=None)
    old = ProviderPaper(provider_record_id="old", title="Old", year=2019)
    new = ProviderPaper(provider_record_id="new", title="New", year=2027)
    filters = LiteratureFilters(year_min=2020, year_max=2026)
    assert ArxivProvider._within_years(unknown, filters) is True
    assert ArxivProvider._within_years(old, filters) is False
    assert ArxivProvider._within_years(new, filters) is False
