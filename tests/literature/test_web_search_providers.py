from __future__ import annotations

from typing import Any

import pytest

from paperagent.literature.factory import LiteratureProviderSettings, build_literature_runtime
from paperagent.literature.merge import merge_provider_results
from paperagent.literature.providers import DuckDuckGoProvider, HTTPResponse, TavilyProvider
from paperagent.literature.verification import VerificationService
from paperagent.schemas.literature import LiteratureFilters, QueryLane


class StubTransport:
    def __init__(self, responses: list[HTTPResponse]) -> None:
        self.responses = list(responses)
        self.posts: list[dict[str, Any]] = []

    async def get(self, *args: Any, **kwargs: Any) -> HTTPResponse:
        raise AssertionError("unexpected GET")

    async def post(self, url: str, **kwargs: Any) -> HTTPResponse:
        self.posts.append({"url": url, **kwargs})
        return self.responses.pop(0)


def _lane() -> QueryLane:
    return QueryLane(
        lane_id="lane-web",
        purpose="method",
        query="lightweight UAV small object detection",
        source_preferences=["tavily", "duckduckgo"],
        gap_ids=["gap-small-object"],
    )


@pytest.mark.asyncio
async def test_tavily_normalizes_result_and_does_not_self_verify_web_page() -> None:
    transport = StubTransport(
        [
            HTTPResponse(
                status_code=200,
                headers={},
                json_data={
                    "results": [
                        {
                            "title": "Example detector project page",
                            "url": "https://example.org/project",
                            "content": "Project summary without a DOI.",
                            "score": 0.8,
                        }
                    ]
                },
                text="",
            )
        ]
    )
    result = await TavilyProvider(api_key="tvly-test", transport=transport).search(
        lane=_lane(), filters=LiteratureFilters(), limit=5
    )

    assert result.status == "success"
    assert result.papers[0].raw_metadata["source_kind"] == "web"
    assert transport.posts[0]["headers"]["Authorization"] == "Bearer tvly-test"
    assert transport.posts[0]["json_body"]["search_depth"] == "basic"
    assert transport.posts[0]["json_body"]["auto_parameters"] is False
    assert transport.posts[0]["json_body"]["max_results"] == 5
    assert "arxiv.org" in transport.posts[0]["json_body"]["include_domains"]

    records = merge_provider_results([result])
    verified = await VerificationService([]).verify_all(records)
    assert verified[0].verification_status == "pending"


@pytest.mark.asyncio
async def test_tavily_extracts_doi_for_existing_verifier_pipeline() -> None:
    transport = StubTransport(
        [
            HTTPResponse(
                status_code=200,
                headers={},
                json_data={
                    "results": [
                        {
                            "title": "Paper landing page",
                            "url": "https://doi.org/10.1234/example.1",
                            "content": "Metadata for the paper.",
                            "score": 0.9,
                        }
                    ]
                },
                text="",
            )
        ]
    )
    result = await TavilyProvider(api_key="tvly-test", transport=transport).search(
        lane=_lane(), filters=LiteratureFilters(), limit=5
    )
    assert result.papers[0].doi == "10.1234/example.1"


@pytest.mark.asyncio
async def test_duckduckgo_parses_html_and_unwraps_redirect() -> None:
    redirect = "//duckduckgo.com/l/?uddg=https%3A%2F%2Farxiv.org%2Fabs%2F2401.01234"
    html = f"""
    <html><body>
      <div class="result">
        <a class="result__a" href="{redirect}">
          Useful arXiv paper
        </a>
        <a class="result__snippet">A useful lightweight detection paper.</a>
      </div>
    </body></html>
    """
    transport = StubTransport(
        [HTTPResponse(status_code=200, headers={}, json_data=None, text=html)]
    )
    result = await DuckDuckGoProvider(transport=transport).search(
        lane=_lane(), filters=LiteratureFilters(), limit=5
    )

    assert result.status == "success"
    assert result.papers[0].arxiv_id == "2401.01234"
    assert result.papers[0].urls == ["https://arxiv.org/abs/2401.01234"]


@pytest.mark.asyncio
async def test_duckduckgo_bot_challenge_is_isolated_as_provider_failure() -> None:
    transport = StubTransport(
        [
            HTTPResponse(
                status_code=200,
                headers={},
                json_data=None,
                text="Unfortunately, bots use DuckDuckGo too",
            )
        ]
    )
    result = await DuckDuckGoProvider(transport=transport).search(
        lane=_lane(), filters=LiteratureFilters(), limit=5
    )
    assert result.status == "failed"
    assert result.error_code == "BOT_BLOCKED"


def test_factory_registers_academic_sources_first_and_web_sources_as_optional() -> None:
    transport = StubTransport([])
    runtime = build_literature_runtime(
        LiteratureProviderSettings(
            enable_web_search=True,
            tavily_api_key="tvly-test",
        ),
        transport=transport,
    )
    assert runtime.service.provider_names == (
        "openalex",
        "semantic_scholar",
        "arxiv",
        "tavily",
        "duckduckgo",
    )
