from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.literature.cache import InMemoryProviderCache
from paperagent.literature.providers import (
    ArxivProvider,
    AsyncHTTPTransport,
    HttpxTransport,
    LiteratureProvider,
    OpenAlexProvider,
    SemanticScholarProvider,
)
from paperagent.literature.service import (
    DeterministicFocusedQueryRewriter,
    LiteratureRetrievalService,
)
from paperagent.literature.verification import (
    CrossrefVerifier,
    DataCiteVerifier,
    VerificationService,
)


class LiteratureProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contact_email: str | None = None
    semantic_scholar_api_key: str | None = None
    provider_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    round_deadline_seconds: float = Field(default=25.0, gt=0, le=120)
    success_cache_ttl_seconds: float = Field(default=3600.0, gt=0)
    empty_cache_ttl_seconds: float = Field(default=120.0, gt=0)
    enable_arxiv_fallback: bool = False


@dataclass(frozen=True)
class LiteratureRuntime:
    service: LiteratureRetrievalService
    adapter: LiteratureSearchAdapter
    transport: AsyncHTTPTransport
    owns_transport: bool

    async def aclose(self) -> None:
        if self.owns_transport and isinstance(self.transport, HttpxTransport):
            await self.transport.aclose()


def build_literature_runtime(
    settings: LiteratureProviderSettings | None = None,
    *,
    transport: AsyncHTTPTransport | None = None,
) -> LiteratureRuntime:
    resolved = settings or LiteratureProviderSettings()
    shared_transport = transport or HttpxTransport()
    providers: list[LiteratureProvider] = [
        OpenAlexProvider(
            transport=shared_transport,
            mailto=resolved.contact_email,
            timeout_seconds=resolved.provider_timeout_seconds,
        ),
        SemanticScholarProvider(
            transport=shared_transport,
            api_key=resolved.semantic_scholar_api_key,
            timeout_seconds=resolved.provider_timeout_seconds,
        ),
        ArxivProvider(
            transport=shared_transport,
            timeout_seconds=resolved.provider_timeout_seconds,
        ),
    ]
    verifier = VerificationService(
        [
            CrossrefVerifier(
                transport=shared_transport,
                timeout_seconds=resolved.provider_timeout_seconds,
                mailto=resolved.contact_email,
            ),
            DataCiteVerifier(
                transport=shared_transport,
                timeout_seconds=resolved.provider_timeout_seconds,
            ),
        ]
    )
    service = LiteratureRetrievalService(
        providers=providers,
        verifier=verifier,
        cache=InMemoryProviderCache(
            success_ttl=resolved.success_cache_ttl_seconds,
            empty_ttl=resolved.empty_cache_ttl_seconds,
        ),
        rewriter=DeterministicFocusedQueryRewriter(),
        total_deadline_seconds=resolved.round_deadline_seconds,
    )
    fallback_preferences = ["arxiv", "openalex"] if resolved.enable_arxiv_fallback else None
    return LiteratureRuntime(
        service=service,
        adapter=LiteratureSearchAdapter(
            service=service,
            fallback_source_preferences=fallback_preferences,
        ),
        transport=shared_transport,
        owns_transport=transport is None,
    )
