from __future__ import annotations

from typing import Any

from paperagent.literature.normalize import canonical_doi
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


class OpenAlexProvider:
    provider_name = "openalex"
    contract_version = "2026-07"
    endpoint = "https://api.openalex.org/works"
    _selected_fields = (
        "id,display_name,publication_year,abstract_inverted_index,authorships,"
        "primary_location,doi,cited_by_count,type,language"
    )

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        mailto: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._mailto = mailto
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
            "search": lane.query,
            "per-page": min(limit, 100 if self._api_key else 10),
            "select": self._selected_fields,
        }
        filter_parts: list[str] = []
        if filters.year_min is not None:
            filter_parts.append(f"from_publication_date:{filters.year_min}-01-01")
        if filters.year_max is not None:
            filter_parts.append(f"to_publication_date:{filters.year_max}-12-31")
        if filter_parts:
            params["filter"] = ",".join(filter_parts)
        if self._mailto:
            params["mailto"] = self._mailto
        if self._api_key:
            params["api_key"] = self._api_key
        try:
            response = await self._transport.get(
                self.endpoint, params=params, timeout=self._timeout
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
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="MALFORMED_RESPONSE",
                message="OpenAlex response missing results list",
            )
        try:
            papers = [self._parse_work(item, lane) for item in data["results"][:limit]]
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
    def _abstract(index: Any) -> str | None:
        if not isinstance(index, dict):
            return None
        positions: list[tuple[int, str]] = []
        for word, raw_positions in index.items():
            if isinstance(word, str) and isinstance(raw_positions, list):
                for position in raw_positions:
                    if isinstance(position, int):
                        positions.append((position, word))
        return " ".join(word for _, word in sorted(positions)) or None

    @classmethod
    def _parse_work(cls, item: Any, lane: QueryLane) -> ProviderPaper:
        if not isinstance(item, dict):
            raise TypeError("OpenAlex work must be an object")
        raw_id = str(item["id"])
        openalex_id = raw_id.rsplit("/", 1)[-1]
        authors: list[str] = []
        for authorship in item.get("authorships") or []:
            if isinstance(authorship, dict):
                author = authorship.get("author")
                if isinstance(author, dict) and author.get("display_name"):
                    authors.append(str(author["display_name"]))
        raw_primary = item.get("primary_location")
        primary: dict[str, Any] = raw_primary if isinstance(raw_primary, dict) else {}
        raw_source = primary.get("source")
        source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
        urls = [str(value) for value in [primary.get("landing_page_url"), item.get("doi")] if value]
        return ProviderPaper(
            provider_record_id=openalex_id,
            title=str(item["display_name"]).strip(),
            authors=authors,
            year=(
                item.get("publication_year")
                if isinstance(item.get("publication_year"), int)
                else None
            ),
            abstract=cls._abstract(item.get("abstract_inverted_index")),
            venue=str(source.get("display_name")) if source.get("display_name") else None,
            doi=canonical_doi(str(item["doi"])) if item.get("doi") else None,
            openalex_id=openalex_id,
            urls=urls,
            citation_count=int(item.get("cited_by_count") or 0),
            publication_type=str(item.get("type")) if item.get("type") else None,
            language=str(item.get("language")) if item.get("language") else None,
            matched_gap_ids=list(lane.gap_ids),
            source_lane_ids=[lane.lane_id],
        )
