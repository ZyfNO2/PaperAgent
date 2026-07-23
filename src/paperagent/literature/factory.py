from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.literature.cache import (
    InMemoryProviderCache,
    JsonFixtureProviderCache,
    LayeredProviderCache,
    ProviderCache,
    SQLiteProviderCache,
)
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
from paperagent.literature.resilience import ProviderCircuitBreaker, ProviderCircuitPolicy
from paperagent.literature.service import (
    DeterministicFocusedQueryRewriter,
    LiteratureRetrievalService,
)
from paperagent.literature.verification import (
    CrossrefVerifier,
    DataCiteVerifier,
    JsonVerificationAttemptCache,
    LayeredVerificationAttemptCache,
    SQLiteVerificationAttemptCache,
    VerificationAttemptCache,
    VerificationService,
)


class LiteratureProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contact_email: str | None = None
    openalex_api_key: str | None = None
    semantic_scholar_api_key: str | None = None
    tavily_api_key: str | None = None
    retrieval_mode: Literal["offline", "cache_first", "live"] = "cache_first"
    cache_database_path: str | None = ".paperagent/retrieval-cache.sqlite3"
    fixture_directory: str | None = None
    record_fixtures: bool = False
    provider_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    arxiv_connect_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    arxiv_read_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    round_deadline_seconds: float = Field(default=25.0, gt=0, le=120)
    success_cache_ttl_seconds: float = Field(default=7 * 24 * 60 * 60, gt=0)
    empty_cache_ttl_seconds: float = Field(default=6 * 60 * 60, gt=0)
    rate_limit_cache_ttl_seconds: float = Field(default=15 * 60, ge=0)
    timeout_cache_ttl_seconds: float = Field(default=3 * 60, ge=0)
    stale_cache_max_age_seconds: float = Field(default=30 * 24 * 60 * 60, ge=0)
    results_per_provider_request: int = Field(default=10, ge=1, le=100)
    max_provider_calls_total: int | None = Field(default=48, ge=1, le=1000)
    max_verification_calls_total: int | None = Field(default=96, ge=1, le=2000)
    openalex_max_concurrency: int = Field(default=2, ge=1, le=10)
    semantic_scholar_max_concurrency: int = Field(default=1, ge=1, le=10)
    arxiv_max_concurrency: int = Field(default=1, ge=1, le=10)
    openalex_requests_per_minute: int = Field(default=120, ge=1, le=6000)
    semantic_scholar_requests_per_minute: int = Field(default=48, ge=1, le=600)
    arxiv_requests_per_minute: int = Field(default=18, ge=1, le=60)
    circuit_timeout_failures: int = Field(default=2, ge=1, le=10)
    circuit_rate_limit_failures: int = Field(default=2, ge=1, le=10)
    circuit_timeout_cooldown_seconds: float = Field(default=10 * 60, gt=0, le=24 * 60 * 60)
    circuit_rate_limit_cooldown_seconds: float = Field(
        default=15 * 60, gt=0, le=24 * 60 * 60
    )
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
        self.service.close()
        if self.owns_transport and isinstance(self.transport, HttpxTransport):
            await self.transport.aclose()


def _build_cache(settings: LiteratureProviderSettings) -> ProviderCache:
    layers: list[ProviderCache] = [
        InMemoryProviderCache(
            success_ttl=settings.success_cache_ttl_seconds,
            empty_ttl=settings.empty_cache_ttl_seconds,
            rate_limit_ttl=settings.rate_limit_cache_ttl_seconds,
            timeout_ttl=settings.timeout_cache_ttl_seconds,
        )
    ]
    if settings.fixture_directory is not None:
        layers.append(
            JsonFixtureProviderCache(
                Path(settings.fixture_directory),
                writable=settings.record_fixtures,
            )
        )
    if settings.cache_database_path is not None:
        layers.append(
            SQLiteProviderCache(
                Path(settings.cache_database_path),
                success_ttl=settings.success_cache_ttl_seconds,
                empty_ttl=settings.empty_cache_ttl_seconds,
                rate_limit_ttl=settings.rate_limit_cache_ttl_seconds,
                timeout_ttl=settings.timeout_cache_ttl_seconds,
            )
        )
    return layers[0] if len(layers) == 1 else LayeredProviderCache(layers)


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
            api_key=resolved.openalex_api_key,
            timeout_seconds=resolved.provider_timeout_seconds,
        ),
        SemanticScholarProvider(
            transport=shared_transport,
            api_key=resolved.semantic_scholar_api_key,
            timeout_seconds=resolved.provider_timeout_seconds,
        ),
        ArxivProvider(
            transport=shared_transport,
            connect_timeout_seconds=resolved.arxiv_connect_timeout_seconds,
            read_timeout_seconds=resolved.arxiv_read_timeout_seconds,
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
    verification_layers: list[VerificationAttemptCache] = []
    if resolved.fixture_directory is not None:
        verification_layers.append(
            JsonVerificationAttemptCache(
                Path(resolved.fixture_directory),
                writable=resolved.record_fixtures,
            )
        )
    if resolved.cache_database_path is not None:
        verification_layers.append(
            SQLiteVerificationAttemptCache(Path(resolved.cache_database_path))
        )
    verification_cache = (
        None
        if not verification_layers
        else (
            verification_layers[0]
            if len(verification_layers) == 1
            else LayeredVerificationAttemptCache(verification_layers)
        )
    )
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
        mode=resolved.retrieval_mode,
        cache=verification_cache,
    )
    cache = _build_cache(resolved)
    circuit_policy = ProviderCircuitPolicy(
        timeout_failures=resolved.circuit_timeout_failures,
        rate_limit_failures=resolved.circuit_rate_limit_failures,
        failure_cooldown_seconds=resolved.circuit_timeout_cooldown_seconds,
        rate_limit_cooldown_seconds=resolved.circuit_rate_limit_cooldown_seconds,
    )
    service = LiteratureRetrievalService(
        providers=providers,
        verifier=verifier,
        cache=cache,
        rewriter=DeterministicFocusedQueryRewriter(),
        total_deadline_seconds=resolved.round_deadline_seconds,
        results_per_request=resolved.results_per_provider_request,
        provider_concurrency={
            "openalex": resolved.openalex_max_concurrency,
            "semantic_scholar": resolved.semantic_scholar_max_concurrency,
            "arxiv": resolved.arxiv_max_concurrency,
            **{name: 1 for name in web_sources},
        },
        request_rates_per_minute={
            "openalex": resolved.openalex_requests_per_minute,
            "semantic_scholar": resolved.semantic_scholar_requests_per_minute,
            "arxiv": resolved.arxiv_requests_per_minute,
        },
        circuit_breaker=ProviderCircuitBreaker(
            {provider.provider_name: circuit_policy for provider in providers}
        ),
        retrieval_mode=resolved.retrieval_mode,
        stale_cache_max_age_seconds=resolved.stale_cache_max_age_seconds,
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
