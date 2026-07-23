from __future__ import annotations

from typing import Any

from paperagent.literature.normalize import canonical_arxiv_id, canonical_doi
from paperagent.literature.providers.base import (
    AsyncHTTPTransport,
    HttpxTransport,
    http_failure_result,
    make_request_id,
    response_failure,
    response_success,
    transport_exception_result,
    utc_now,
)
from paperagent.schemas.literature import (
    LiteratureFilters,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)


class SemanticScholarProvider:
    provider_name = "semantic_scholar"
    contract_version = "graph-v1-2026-07"
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._api_key = api_key
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
        params: dict[str, str | int] = {
            "query": lane.query,
            "limit": min(limit, 100),
            "fields": (
                "paperId,title,abstract,year,authors,externalIds,venue,url,"
                "citationCount,publicationTypes"
            ),
        }
        if filters.year_min is not None or filters.year_max is not None:
            start = filters.year_min or ""
            end = filters.year_max or ""
            params["year"] = f"{start}-{end}"
        headers = {"x-api-key": self._api_key} if self._api_key else None
        try:
            response = await self._transport.get(
                self.endpoint,
                params=params,
                headers=headers,
                timeout=self._timeout,
            )
        except Exception as exc:
            return transport_exception_result(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                exc=exc,
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
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="MALFORMED_RESPONSE",
                message="Semantic Scholar response missing data list",
            )
        try:
            papers = [self._parse_paper(item, lane) for item in data["data"][:limit]]
        except (KeyError, TypeError, ValueError) as exc:
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
    def _parse_paper(item: Any, lane: QueryLane) -> ProviderPaper:
        if not isinstance(item, dict):
            raise TypeError("Semantic Scholar paper must be an object")
        raw_external = item.get("externalIds")
        external: dict[str, Any] = raw_external if isinstance(raw_external, dict) else {}
        authors = [
            str(author["name"])
            for author in item.get("authors") or []
            if isinstance(author, dict) and author.get("name")
        ]
        publication_types = item.get("publicationTypes") or []
        publication_type = (
            str(publication_types[0])
            if isinstance(publication_types, list) and publication_types
            else None
        )
        url = str(item["url"]) if item.get("url") else None
        return ProviderPaper(
            provider_record_id=str(item["paperId"]),
            title=str(item["title"]).strip(),
            authors=authors,
            year=item.get("year") if isinstance(item.get("year"), int) else None,
            abstract=str(item["abstract"]).strip() if item.get("abstract") else None,
            venue=str(item["venue"]).strip() if item.get("venue") else None,
            doi=canonical_doi(str(external["DOI"])) if external.get("DOI") else None,
            arxiv_id=canonical_arxiv_id(str(external["ArXiv"])) if external.get("ArXiv") else None,
            semantic_scholar_id=str(item["paperId"]),
            urls=[url] if url else [],
            citation_count=int(item.get("citationCount") or 0),
            publication_type=publication_type,
            matched_gap_ids=list(lane.gap_ids),
            source_lane_ids=[lane.lane_id],
        )
