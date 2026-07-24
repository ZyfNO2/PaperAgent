from __future__ import annotations

from dataclasses import dataclass

import pytest

from paperagent.literature.factory import (
    LiteratureProviderSettings,
    build_literature_runtime,
)
from paperagent.literature.providers.base import HTTPResponse


@dataclass
class EmptyTransport:
    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        del url, params, headers, timeout
        return HTTPResponse(status_code=200, headers={}, json_data={}, text="")


def test_factory_builds_all_discovery_providers_without_secrets() -> None:
    transport = EmptyTransport()
    runtime = build_literature_runtime(
        LiteratureProviderSettings(contact_email="dev@example.test"),
        transport=transport,
    )
    assert runtime.service.provider_names == (
        "openalex",
        "semantic_scholar",
        "arxiv",
    )
    assert runtime.transport is transport
    assert runtime.owns_transport is False


@pytest.mark.asyncio
async def test_runtime_does_not_close_injected_transport() -> None:
    runtime = build_literature_runtime(transport=EmptyTransport())
    await runtime.aclose()


@pytest.mark.asyncio
async def test_runtime_closes_owned_http_transport() -> None:
    runtime = build_literature_runtime()
    assert runtime.owns_transport is True
    await runtime.aclose()
