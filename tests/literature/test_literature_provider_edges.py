from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import pytest

from paperagent.literature.providers.arxiv import ArxivProvider
from paperagent.literature.providers.base import (
    HTTPResponse,
    HttpxTransport,
    http_failure_result,
    make_request_id,
)
from paperagent.literature.providers.openalex import OpenAlexProvider
from paperagent.literature.providers.semantic_scholar import SemanticScholarProvider
from paperagent.schemas.literature import LiteratureFilters, QueryLane

NOW = datetime(2026, 1, 1, tzinfo=UTC)
LANE = QueryLane(
    lane_id="edge",
    purpose="recent_progress",
    query="recent retrieval systems",
    gap_ids=["g1"],
)
FILTERS = LiteratureFilters(year_min=2023, year_max=2026)


@dataclass
class CaptureTransport:
    responses: list[HTTPResponse | Exception]
    calls: list[tuple[str, dict[str, str | int] | None, dict[str, str] | None]] = field(
        default_factory=list
    )

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        del timeout
        self.calls.append((url, params, headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
async def test_httpx_transport_parses_json_and_non_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/json":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, text="plain")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport(client)
    parsed = await transport.get("https://example.test/json")
    plain = await transport.get("https://example.test/plain")
    assert parsed.json_data == {"ok": True}
    assert plain.json_data is None
    assert plain.text == "plain"
    await transport.aclose()
    await client.aclose()

    owned = HttpxTransport()
    await owned.aclose()


def test_request_id_is_stable_and_changes_with_filter() -> None:
    first = make_request_id("openalex", LANE, FILTERS, 10)
    second = make_request_id("openalex", LANE, FILTERS, 10)
    changed = make_request_id("openalex", LANE, LiteratureFilters(year_min=2024, year_max=2026), 10)
    assert first == second
    assert changed != first


def test_http_failure_mapper_handles_rate_limit_server_error_and_success() -> None:
    rate = http_failure_result(
        provider="p",
        request_id="r1",
        started_at=NOW,
        response=HTTPResponse(429, {}, {}, ""),
    )
    server = http_failure_result(
        provider="p",
        request_id="r2",
        started_at=NOW,
        response=HTTPResponse(503, {}, {}, ""),
    )
    success = http_failure_result(
        provider="p",
        request_id="r3",
        started_at=NOW,
        response=HTTPResponse(200, {}, {}, ""),
    )
    assert rate is not None and rate.status == "rate_limited"
    assert server is not None and server.error_code == "HTTP_503"
    assert success is None


@pytest.mark.asyncio
async def test_openalex_builds_year_and_mailto_filters() -> None:
    transport = CaptureTransport([HTTPResponse(200, {}, {"results": []}, "")])
    result = await OpenAlexProvider(transport=transport, mailto="dev@example.test").search(
        lane=LANE,
        filters=FILTERS,
        limit=50,
    )
    assert result.status == "empty"
    _, params, _ = transport.calls[0]
    assert params is not None
    assert params["per-page"] == 10
    assert params["mailto"] == "dev@example.test"
    assert "from_publication_date:2023-01-01" in str(params["filter"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (RuntimeError("network"), "TRANSPORT_ERROR"),
        (HTTPResponse(500, {}, {}, ""), "HTTP_500"),
        (HTTPResponse(200, {}, {"results": [{}]}, ""), "MALFORMED_RESPONSE"),
    ],
)
async def test_openalex_failure_paths_are_explicit(
    response: HTTPResponse | Exception, code: str
) -> None:
    result = await OpenAlexProvider(transport=CaptureTransport([response])).search(
        lane=LANE,
        filters=FILTERS,
        limit=10,
    )
    assert result.status == "failed"
    assert result.error_code == code


@pytest.mark.asyncio
async def test_semantic_scholar_normalizes_success_payload_and_api_key() -> None:
    transport = CaptureTransport(
        [
            HTTPResponse(
                200,
                {},
                {
                    "data": [
                        {
                            "paperId": "S1",
                            "title": "Reliable Retrieval",
                            "abstract": "Detailed abstract",
                            "year": 2025,
                            "authors": [{"name": "Jane Doe"}],
                            "externalIds": {"DOI": "10.1/ABC", "ArXiv": "2501.00001v1"},
                            "venue": "IRConf",
                            "url": "https://example.test/s1",
                            "citationCount": 2,
                            "publicationTypes": ["Conference"],
                        }
                    ]
                },
                "",
            )
        ]
    )
    result = await SemanticScholarProvider(transport=transport, api_key="secret").search(
        lane=LANE,
        filters=FILTERS,
        limit=10,
    )
    assert result.status == "success"
    paper = result.papers[0]
    assert paper.doi == "10.1/abc"
    assert paper.arxiv_id == "2501.00001"
    assert paper.publication_type == "Conference"
    _, params, headers = transport.calls[0]
    assert params is not None and params["year"] == "2023-2026"
    assert headers == {"x-api-key": "secret"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "status", "code"),
    [
        (TimeoutError("slow"), "timeout", "TIMEOUT"),
        (RuntimeError("network"), "failed", "TRANSPORT_ERROR"),
        (HTTPResponse(500, {}, {}, ""), "failed", "HTTP_500"),
        (HTTPResponse(200, {}, {"data": [{}]}, ""), "failed", "MALFORMED_RESPONSE"),
    ],
)
async def test_semantic_scholar_failure_paths(
    response: HTTPResponse | Exception, status: str, code: str
) -> None:
    result = await SemanticScholarProvider(transport=CaptureTransport([response])).search(
        lane=LANE,
        filters=FILTERS,
        limit=10,
    )
    assert result.status == status
    assert result.error_code == code


@pytest.mark.asyncio
async def test_arxiv_empty_and_year_filter_are_verified_empty() -> None:
    xml = """<feed xmlns='http://www.w3.org/2005/Atom'>
      <entry>
        <id>http://arxiv.org/abs/1901.00001</id>
        <title>Old retrieval</title>
        <summary>Old</summary>
        <published>2019-01-01T00:00:00Z</published>
        <author><name>Jane Doe</name></author>
      </entry>
    </feed>"""
    result = await ArxivProvider(
        transport=CaptureTransport([HTTPResponse(200, {}, None, xml)])
    ).search(lane=LANE, filters=FILTERS, limit=10)
    assert result.status == "empty"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "status", "code"),
    [
        (TimeoutError("slow"), "timeout", "TIMEOUT"),
        (RuntimeError("network"), "failed", "TRANSPORT_ERROR"),
        (HTTPResponse(503, {}, {}, ""), "failed", "HTTP_503"),
        (HTTPResponse(200, {}, None, "<bad>"), "failed", "MALFORMED_RESPONSE"),
        (
            HTTPResponse(
                200,
                {},
                None,
                "<feed xmlns='http://www.w3.org/2005/Atom'><entry><title>x</title></entry></feed>",
            ),
            "failed",
            "MALFORMED_RESPONSE",
        ),
    ],
)
async def test_arxiv_failure_paths(
    response: HTTPResponse | Exception, status: str, code: str
) -> None:
    result = await ArxivProvider(transport=CaptureTransport([response])).search(
        lane=LANE,
        filters=FILTERS,
        limit=10,
    )
    assert result.status == status
    assert result.error_code == code
