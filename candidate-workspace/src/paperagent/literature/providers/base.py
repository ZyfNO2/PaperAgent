from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

import httpx

from paperagent.schemas.literature import (
    LiteratureFilters,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    json_data: Any | None
    text: str


class AsyncHTTPTransport(Protocol):
    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse: ...

    async def post(
        self,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse: ...


class LiteratureProvider(Protocol):
    provider_name: str
    contract_version: str

    async def search(
        self,
        *,
        lane: QueryLane,
        filters: LiteratureFilters,
        limit: int,
    ) -> ProviderResult: ...


class HttpxTransport:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(follow_redirects=True)
        self._owns_client = client is None

    @staticmethod
    def _response(response: httpx.Response) -> HTTPResponse:
        try:
            json_data: Any | None = response.json()
        except ValueError:
            json_data = None
        return HTTPResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            json_data=json_data,
            text=response.text,
        )

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        response = await self._client.get(url, params=params, headers=headers, timeout=timeout)
        return self._response(response)

    async def post(
        self,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        response = await self._client.post(
            url,
            json=json_body,
            data=data,
            headers=headers,
            timeout=timeout,
        )
        return self._response(response)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def utc_now() -> datetime:
    return datetime.now(UTC)


def make_request_id(
    provider: str,
    lane: QueryLane,
    filters: LiteratureFilters,
    limit: int,
) -> str:
    raw = "|".join(
        [
            provider,
            lane.query.strip().lower(),
            ",".join(sorted(lane.gap_ids)),
            str(filters.year_min),
            str(filters.year_max),
            ",".join(sorted(filters.languages)),
            ",".join(sorted(filters.publication_types)),
            str(limit),
        ]
    )
    return f"req-{provider}-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def response_failure(
    *,
    provider: str,
    request_id: str,
    started_at: datetime,
    status: str,
    code: str,
    message: str,
) -> ProviderResult:
    normalized_status = status if status in {"rate_limited", "timeout", "failed"} else "failed"
    return ProviderResult(
        provider=provider,
        request_id=request_id,
        status=normalized_status,  # type: ignore[arg-type]
        started_at=started_at,
        finished_at=utc_now(),
        error_code=code,
        error_message=message,
    )


def response_success(
    *,
    provider: str,
    request_id: str,
    started_at: datetime,
    papers: list[ProviderPaper],
) -> ProviderResult:
    return ProviderResult(
        provider=provider,
        request_id=request_id,
        status="success" if papers else "empty",
        papers=papers,
        started_at=started_at,
        finished_at=utc_now(),
    )


def http_failure_result(
    *,
    provider: str,
    request_id: str,
    started_at: datetime,
    response: HTTPResponse,
) -> ProviderResult | None:
    if response.status_code == 429:
        return response_failure(
            provider=provider,
            request_id=request_id,
            started_at=started_at,
            status="rate_limited",
            code="RATE_LIMITED",
            message="provider rate limit exceeded",
        )
    if response.status_code >= 400:
        return response_failure(
            provider=provider,
            request_id=request_id,
            started_at=started_at,
            status="failed",
            code=f"HTTP_{response.status_code}",
            message=f"provider returned HTTP {response.status_code}",
        )
    return None
