from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from paperagent.literature.providers._web import (
    extract_identifiers,
    stable_web_record_id,
    unwrap_duckduckgo_url,
)
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


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        value = next((value for name, value in attrs if name == "class"), None) or ""
        return set(value.split())

    def _flush_capture(self) -> None:
        if self._current is None or self._capture is None:
            self._buffer.clear()
            self._capture = None
            return
        value = " ".join("".join(self._buffer).split())
        if value:
            self._current[self._capture] = value
        self._buffer.clear()
        self._capture = None

    def _flush_result(self) -> None:
        self._flush_capture()
        if self._current and self._current.get("title") and self._current.get("url"):
            self.results.append(self._current)
        self._current = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = self._classes(attrs)
        if tag == "a" and "result__a" in classes:
            self._flush_result()
            href = next((value for name, value in attrs if name == "href"), None) or ""
            self._current = {"url": unwrap_duckduckgo_url(href)}
            self._capture = "title"
            self._buffer = []
        elif self._current is not None and "result__snippet" in classes:
            self._flush_capture()
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"a", "div"} and self._capture is not None:
            self._flush_capture()

    def close(self) -> None:
        super().close()
        self._flush_result()


class DuckDuckGoProvider:
    provider_name = "duckduckgo"
    contract_version = "html-2026-07"
    endpoint = "https://html.duckduckgo.com/html/"

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
        try:
            response = await self._transport.post(
                self.endpoint,
                data={"q": lane.query, "b": ""},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "Chrome/124.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://html.duckduckgo.com/",
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
                message="DuckDuckGo request timed out",
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
        lowered = response.text.casefold()
        if any(
            marker in lowered
            for marker in (
                "unfortunately, bots use duckduckgo too",
                "anomaly-modal",
                "bot challenge",
            )
        ):
            return response_failure(
                provider=self.provider_name,
                request_id=request_id,
                started_at=started,
                status="failed",
                code="BOT_BLOCKED",
                message="DuckDuckGo HTML endpoint returned a bot challenge",
            )
        parser = _DuckDuckGoHTMLParser()
        try:
            parser.feed(response.text)
            parser.close()
            papers = [self._parse_result(item, lane) for item in parser.results[:limit]]
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
    def _parse_result(item: dict[str, Any], lane: QueryLane) -> ProviderPaper:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        if not title or not url:
            raise ValueError("DuckDuckGo result requires title and URL")
        doi, arxiv_id = extract_identifiers(url, title, snippet)
        return ProviderPaper(
            provider_record_id=stable_web_record_id(url, title),
            title=title,
            abstract=snippet or None,
            doi=doi,
            arxiv_id=arxiv_id,
            urls=[url],
            matched_gap_ids=list(lane.gap_ids),
            source_lane_ids=[lane.lane_id],
            publication_type="web_result",
            raw_metadata={
                "source_kind": "web",
                "web_provider": "duckduckgo",
            },
        )
