from __future__ import annotations

from typing import Any

from paperagent.literature.providers._web import extract_identifiers, stable_web_record_id
from paperagent.literature.providers.base import (
    AsyncHTTPTransport,
    HttpxTransport,
    http_failure_result,
    make_request_id,
    response_failure,
    response_success,
    utc_now,
)
from paperagent.schemas.literature import (
    LiteratureFilters,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)


class TavilyProvider:
    provider_name = "tavily"
    contract_version = "2026-07"
    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        *,
        api_key: str,
        transport: AsyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Tavily API key must not be empty")
        self._api_key = api_key
        self._transport = transport or HttpxTransport()
        self._timeout = timeout_seconds

    async def search(
        self,
        *,
        lane: QueryLane,
        filters: LiteratureFilters,
        limit: int,
    ) -> ProviderResult:
        started = utc_now()
        request_id = make_request_id(self.provider_name, lane, filters, limit)
        try:
            response = await self._transport.post(
                self.endpoint,
                json_body={
                    "query": lane.query,
                    "search_depth": "basic",
                    "max_results": min(limit, 10),
                    "topic": "general",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                    "auto_parameters": False,
                    "include_usage": False,
                },
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "PaperAgent/0.9 web-search",
                },
                timeout=self._timeout,
            )
        except TimeoutError:
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="timeout",
                code="TIMEOUT",
                message="Tavily request timed out",
            )
        except Exception as exc:
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="TRANSPORT_ERROR",
                message=str(exc),
            )
        failure = http_failure_result(
            provider=self.provider_name,
            request_id=request_id,
            started_at=started,
            response=response,
        )
        if failure is not None:
            return failure
        data = response.json_data
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="MALFORMED_RESPONSE",
                message="Tavily response missing results list",
            )
        try:
            papers = [self._parse_result(item, lane) for item in data["results"][:limit]]
        except (TypeError, ValueError) as exc:
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="MALFORMED_RESPONSE",
                message=str(exc),
            )
        return response_success(
            provider=self.provider_name,
            request_id=request_id,
            started_at=started,
            papers=papers,
        )

    @staticmethod
    def _parse_result(item: Any, lane: QueryLane) -> ProviderPaper:
        if not isinstance(item, dict):
            raise TypeError("Tavily result must be an object")
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not url:
            raise ValueError("Tavily result requires title and URL")
        doi, arxiv_id = extract_identifiers(url, title, content)
        raw_score = item.get("score")
        score = float(raw_score) if isinstance(raw_score, int | float) else None
        return ProviderPaper(
            provider_record_id=stable_web_record_id(url, title),
            title=title,
            abstract=content or None,
            doi=doi,
            arxiv_id=arxiv_id,
            urls=[url],
            matched_gap_ids=list(lane.gap_ids),
            source_lane_ids=[lane.lane_id],
            publication_type="web_result",
            raw_metadata={
                "source_kind": "web",
                "web_provider": "tavily",
                "relevance_score": score,
            },
        )
