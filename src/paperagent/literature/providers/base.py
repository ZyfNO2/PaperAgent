from __future__ import annotations

import socket
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any, Protocol, TypeAlias

import httpx

from paperagent.schemas.literature import (
    LiteratureFilters,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)

RequestTimeout: TypeAlias = float | httpx.Timeout


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
        timeout: RequestTimeout = 10.0,
    ) -> HTTPResponse: ...

    async def post(
        self,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: RequestTimeout = 10.0,
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
        timeout: RequestTimeout = 10.0,
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
        timeout: RequestTimeout = 10.0,
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
    retry_at: datetime | None = None,
    rate_limit_remaining: int | None = None,
) -> ProviderResult:
    normalized_status = status if status in {"rate_limited", "timeout", "failed"} else "failed"
    return ProviderResult(
        provider=provider,
        request_id=request_id,
        status=normalized_status,  # type: ignore[arg-type]
        started_at=started_at,
        finished_at=utc_now(),
        retry_at=retry_at,
        rate_limit_remaining=rate_limit_remaining,
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


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == target), None)


def _header_int(headers: Mapping[str, str], name: str) -> int | None:
    value = _header(headers, name)
    if value is None:
        return None
    try:
        return max(0, int(value.strip()))
    except ValueError:
        return None


def parse_retry_at(headers: Mapping[str, str], *, now: datetime | None = None) -> datetime | None:
    current = now or utc_now()
    retry_after = _header(headers, "Retry-After")
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(retry_after)
            except (TypeError, ValueError, OverflowError):
                parsed = None
            if parsed is not None:
                return parsed.astimezone(UTC)
        else:
            return current + timedelta(seconds=max(0.0, seconds))

    reset = _header(headers, "X-RateLimit-Reset")
    if reset:
        try:
            raw = float(reset)
        except ValueError:
            return None
        if raw > current.timestamp() + 60:
            return datetime.fromtimestamp(raw, tz=UTC)
        return current + timedelta(seconds=max(0.0, raw))
    return None


def _contains_dns_failure(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, socket.gaierror):
            return True
        current = current.__cause__ or current.__context__
    text = str(exc).casefold()
    return "name resolution" in text or "nodename nor servname" in text


def transport_exception_result(
    *,
    provider: str,
    request_id: str,
    started_at: datetime,
    exc: Exception,
) -> ProviderResult:
    if isinstance(exc, httpx.ConnectTimeout):
        status, code = "timeout", "CONNECTION_TIMEOUT"
    elif isinstance(exc, httpx.ReadTimeout):
        status, code = "timeout", "READ_TIMEOUT"
    elif isinstance(exc, httpx.TimeoutException | TimeoutError):
        status, code = "timeout", "TIMEOUT"
    elif _contains_dns_failure(exc):
        status, code = "failed", "DNS_FAILURE"
    elif isinstance(exc, httpx.ConnectError):
        status, code = "failed", "CONNECTION_FAILURE"
    else:
        status, code = "failed", "TRANSPORT_ERROR"
    return response_failure(
        provider=provider,
        request_id=request_id,
        started_at=started_at,
        status=status,
        code=code,
        message=str(exc) or code,
    )


def http_failure_result(
    *,
    provider: str,
    request_id: str,
    started_at: datetime,
    response: HTTPResponse,
) -> ProviderResult | None:
    if response.status_code == 429:
        remaining = _header_int(response.headers, "X-RateLimit-Remaining")
        retry_at = parse_retry_at(response.headers)
        reset_header = _header(response.headers, "X-RateLimit-Reset")
        code = (
            "DAILY_QUOTA_EXHAUSTED"
            if remaining == 0 and reset_header is not None
            else "RATE_LIMITED"
        )
        return response_failure(
            provider=provider,
            request_id=request_id,
            started_at=started_at,
            status="rate_limited",
            code=code,
            message="provider rate limit exceeded",
            retry_at=retry_at,
            rate_limit_remaining=remaining,
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
