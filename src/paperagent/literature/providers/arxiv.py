from __future__ import annotations

from xml.etree import ElementTree

from paperagent.literature.normalize import canonical_arxiv_id
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

_ATOM = "{http://www.w3.org/2005/Atom}"


class ArxivProvider:
    provider_name = "arxiv"
    contract_version = "atom-2026-01"
    endpoint = "https://export.arxiv.org/api/query"

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
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
        normalized_query = " ".join(lane.query.split())
        escaped_query = normalized_query.replace('"', r"\"")
        search_query = (
            f'ti:"{escaped_query}"' if lane.purpose == "baseline" else f"all:{normalized_query}"
        )
        params: dict[str, str | int] = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(limit, 10),
            "sortBy": "relevance",
        }
        try:
            response = await self._transport.get(
                self.endpoint, params=params, timeout=self._timeout
            )
        except TimeoutError:
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="timeout",
                code="TIMEOUT",
                message="arXiv request timed out",
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
        try:
            root = ElementTree.fromstring(response.text)
            papers = [self._parse_entry(entry, lane) for entry in root.findall(f"{_ATOM}entry")]
        except (ElementTree.ParseError, TypeError, ValueError) as exc:
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="MALFORMED_RESPONSE",
                message=str(exc),
            )
        filtered = [paper for paper in papers if self._within_years(paper, filters)][:limit]
        return response_success(
            provider=self.provider_name,
            request_id=request_id,
            started_at=started,
            papers=filtered,
        )

    @staticmethod
    def _text(entry: ElementTree.Element, name: str) -> str | None:
        element = entry.find(f"{_ATOM}{name}")
        if element is None or element.text is None:
            return None
        return " ".join(element.text.split()) or None

    @classmethod
    def _parse_entry(cls, entry: ElementTree.Element, lane: QueryLane) -> ProviderPaper:
        raw_id = cls._text(entry, "id")
        title = cls._text(entry, "title")
        if raw_id is None or title is None:
            raise ValueError("arXiv entry missing id or title")
        authors = [
            " ".join(name.text.split())
            for author in entry.findall(f"{_ATOM}author")
            for name in author.findall(f"{_ATOM}name")
            if name.text
        ]
        published = cls._text(entry, "published")
        year = int(published[:4]) if published and len(published) >= 4 else None
        urls = [
            str(link.attrib["href"])
            for link in entry.findall(f"{_ATOM}link")
            if link.attrib.get("href")
        ]
        categories = [
            category.attrib["term"]
            for category in entry.findall(f"{_ATOM}category")
            if category.attrib.get("term")
        ]
        arxiv_id = canonical_arxiv_id(raw_id)
        if arxiv_id is None:
            raise ValueError("invalid arXiv identifier")
        return ProviderPaper(
            provider_record_id=arxiv_id,
            title=title,
            authors=authors,
            year=year,
            abstract=cls._text(entry, "summary"),
            venue="arXiv",
            arxiv_id=arxiv_id,
            urls=urls or [raw_id],
            publication_type="preprint",
            matched_gap_ids=list(lane.gap_ids),
            source_lane_ids=[lane.lane_id],
            raw_metadata={"categories": categories},
        )

    @staticmethod
    def _within_years(paper: ProviderPaper, filters: LiteratureFilters) -> bool:
        if paper.year is None:
            return True
        if filters.year_min is not None and paper.year < filters.year_min:
            return False
        return not (filters.year_max is not None and paper.year > filters.year_max)
