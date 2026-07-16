from __future__ import annotations

from dataclasses import dataclass

import pytest

from paperagent.literature.providers.arxiv import ArxivProvider
from paperagent.literature.providers.base import HTTPResponse
from paperagent.literature.providers.openalex import OpenAlexProvider
from paperagent.literature.providers.semantic_scholar import SemanticScholarProvider
from paperagent.schemas.literature import LiteratureFilters, QueryLane


@dataclass
class StaticTransport:
    response: HTTPResponse | Exception
    calls: int = 0

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


LANE = QueryLane(
    lane_id="l1",
    purpose="method",
    query="reliable literature retrieval",
    gap_ids=["g1"],
)
FILTERS = LiteratureFilters(year_min=2020, year_max=2026)


@pytest.mark.asyncio
async def test_openalex_normalizes_paper_and_abstract() -> None:
    transport = StaticTransport(
        HTTPResponse(
            status_code=200,
            headers={},
            json_data={
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "display_name": "Reliable Retrieval",
                        "publication_year": 2024,
                        "doi": "https://doi.org/10.1000/ABC",
                        "authorships": [{"author": {"display_name": "Jane Doe"}}],
                        "primary_location": {
                            "landing_page_url": "https://example.test/paper",
                            "source": {"display_name": "IR Journal"},
                        },
                        "abstract_inverted_index": {"Reliable": [0], "retrieval": [1]},
                        "cited_by_count": 7,
                        "type": "article",
                        "language": "en",
                    }
                ]
            },
            text="",
        )
    )
    result = await OpenAlexProvider(transport=transport).search(
        lane=LANE, filters=FILTERS, limit=10
    )
    assert result.status == "success"
    paper = result.papers[0]
    assert paper.openalex_id == "W1"
    assert paper.abstract == "Reliable retrieval"
    assert paper.doi == "10.1000/abc"
    assert paper.matched_gap_ids == ["g1"]


@pytest.mark.asyncio
async def test_semantic_scholar_empty_is_not_failure() -> None:
    provider = SemanticScholarProvider(
        transport=StaticTransport(
            HTTPResponse(status_code=200, headers={}, json_data={"data": []}, text="")
        )
    )
    result = await provider.search(lane=LANE, filters=FILTERS, limit=10)
    assert result.status == "empty"
    assert result.error_code is None


@pytest.mark.asyncio
async def test_semantic_scholar_rate_limit_is_explicit() -> None:
    provider = SemanticScholarProvider(
        transport=StaticTransport(
            HTTPResponse(status_code=429, headers={"retry-after": "2"}, json_data={}, text="")
        )
    )
    result = await provider.search(lane=LANE, filters=FILTERS, limit=10)
    assert result.status == "rate_limited"
    assert result.error_code == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_arxiv_parses_atom_feed() -> None:
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry>
        <id>http://arxiv.org/abs/2401.12345v2</id>
        <title> Reliable Retrieval </title>
        <summary> A robust method. </summary>
        <published>2024-01-15T00:00:00Z</published>
        <author><name>Jane Doe</name></author>
        <link href='https://arxiv.org/abs/2401.12345'/>
        <category term='cs.IR'/>
      </entry>
    </feed>"""
    provider = ArxivProvider(
        transport=StaticTransport(
            HTTPResponse(status_code=200, headers={}, json_data=None, text=xml)
        )
    )
    result = await provider.search(lane=LANE, filters=FILTERS, limit=10)
    assert result.status == "success"
    paper = result.papers[0]
    assert paper.arxiv_id == "2401.12345"
    assert paper.year == 2024
    assert paper.publication_type == "preprint"


@pytest.mark.asyncio
async def test_provider_timeout_is_not_reported_as_empty() -> None:
    provider = OpenAlexProvider(transport=StaticTransport(TimeoutError("slow")))
    result = await provider.search(lane=LANE, filters=FILTERS, limit=10)
    assert result.status == "timeout"
    assert result.error_code == "TIMEOUT"
    assert result.papers == []


@pytest.mark.asyncio
async def test_malformed_response_is_failed() -> None:
    provider = OpenAlexProvider(
        transport=StaticTransport(
            HTTPResponse(status_code=200, headers={}, json_data={"results": "bad"}, text="")
        )
    )
    result = await provider.search(lane=LANE, filters=FILTERS, limit=10)
    assert result.status == "failed"
    assert result.error_code == "MALFORMED_RESPONSE"
