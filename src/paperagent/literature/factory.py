from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.literature.cache import InMemoryProviderCache
from paperagent.literature.providers import (
    ArxivProvider,
    AsyncHTTPTransport,
    DuckDuckGoProvider,
    HttpxTransport,
    LiteratureProvider,
    OpenAlexProvider,
    SemanticScholarProvider,
    TavilyProvider,
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
    tavily_api_key: str | None = None
    provider_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    round_deadline_seconds: float = Field(default=25.0, gt=0, le=120)
    success_cache_ttl_seconds: float = Field(default=3600.0, gt=0)
    empty_cache_ttl_seconds: float = Field(default=120.0, gt=0)
    results_per_provider_request: int = Field(default=6, ge=1, le=10)
    max_provider_calls_total: int | None = Field(default=48, ge=1, le=1000)
    max_verification_calls_total: int | None = Field(default=96, ge=1, le=2000)
    enable_arxiv_fallback: bool = False
    enable_web_search: bool = False
    enable_duckduckgo: bool = True


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
    web_sources: list[str] = []
    if resolved.enable_web_search:
        if resolved.tavily_api_key:
            providers.append(
                TavilyProvider(
                    api_key=resolved.tavily_api_key,
                    transport=shared_transport,
                    timeout_seconds=resolved.provider_timeout_seconds,
                )
            )
            web_sources.append("tavily")
        if resolved.enable_duckduckgo:
            providers.append(
                DuckDuckGoProvider(
                    transport=shared_transport,
                    timeout_seconds=resolved.provider_timeout_seconds,
                )
            )
            web_sources.append("duckduckgo")
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
        ],
        max_network_calls=resolved.max_verification_calls_total,
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
        results_per_request=resolved.results_per_provider_request,
        max_provider_calls=resolved.max_provider_calls_total,
    )
    return LiteratureRuntime(
        service=service,
        adapter=LiteratureSearchAdapter(
            service=service,
            source_preferences=["openalex", "semantic_scholar"],
            supplement_source_preferences=["arxiv"],
            fallback_source_preferences=web_sources or None,
        ),
        transport=shared_transport,
        owns_transport=transport is None,
    )
