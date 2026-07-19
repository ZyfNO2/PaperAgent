from __future__ import annotations

from paperagent.errors import ProviderError
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.schemas import SearchCandidate, SearchQuery
from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    PaperRecord,
    ProviderResult,
    QueryLane,
)

_ACADEMIC_PROVIDERS = frozenset({"openalex", "semantic_scholar", "arxiv"})
_WEB_PROVIDERS = frozenset({"tavily", "duckduckgo"})


class LiteratureSearchAdapter:
    provider_name = "literature_retrieval"

    def __init__(
        self,
        *,
        service: LiteratureRetrievalService,
        source_preferences: list[str] | None = None,
        supplement_source_preferences: list[str] | None = None,
        fallback_source_preferences: list[str] | None = None,
    ) -> None:
        self._service = service
        self._source_preferences = source_preferences or ["openalex", "semantic_scholar"]
        self._supplement_source_preferences = supplement_source_preferences or []
        self._fallback_source_preferences = fallback_source_preferences
        self._last_results: dict[str, list[ProviderResult]] = {}
        self._last_fallback_used: dict[str, bool] = {}

    async def search(
        self,
        *,
        query: SearchQuery,
        scenario: str,
        call_index: int,
        fixture_version: str,
        limit: int,
    ) -> list[SearchCandidate]:
        del scenario, call_index, fixture_version

        primary = await self._service.retrieve(
            self._build_plan(query, self._source_preferences, lane_suffix="primary")
        )
        provider_results = list(primary.provider_results)
        papers_by_id = {paper.paper_id: paper for paper in primary.papers}

        if self._supplement_source_preferences:
            supplement = await self._service.retrieve(
                self._build_plan(
                    query,
                    self._supplement_source_preferences,
                    lane_suffix="academic-supplement",
                )
            )
            provider_results.extend(supplement.provider_results)
            self._merge_papers(papers_by_id, supplement.papers)

        fallback_used = False
        has_verified = any(
            paper.verification_status == "verified" for paper in papers_by_id.values()
        )
        fallback = self._fallback_source_preferences
        if not has_verified and fallback:
            secondary = await self._service.retrieve(
                self._build_plan(query, fallback, lane_suffix="web-supplement")
            )
            provider_results.extend(secondary.provider_results)
            fallback_used = True
            self._merge_papers(papers_by_id, secondary.papers)

        self._last_results[query.query_id] = provider_results
        self._last_fallback_used[query.query_id] = fallback_used

        if provider_results and all(
            result.status in {"failed", "timeout", "rate_limited"} for result in provider_results
        ):
            raise ProviderError(
                "all literature providers failed",
                provider=self.provider_name,
                task=query.query_id,
                retryable=True,
                code="ALL_LITERATURE_PROVIDERS_FAILED",
            )

        candidates: list[SearchCandidate] = []
        for paper in list(papers_by_id.values())[:limit]:
            locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
            providers = sorted({record.provider for record in paper.source_records})
            provider_set = set(providers)
            source_kind = self._source_kind(provider_set)
            score = paper.rank_features.score if paper.rank_features else 0.0
            candidates.append(
                SearchCandidate(
                    candidate_id=paper.paper_id,
                    query_id=query.query_id,
                    gap_id=query.gap_id,
                    source_type="paper",
                    title=paper.canonical_title,
                    locator=locator,
                    snippet=paper.abstract or paper.canonical_title,
                    provider=self.provider_name,
                    metadata={
                        "verification_status": paper.verification_status,
                        "providers": ",".join(providers),
                        "provider_classes": source_kind,
                        "source_kind": source_kind,
                        "rank_score": f"{score:.6f}",
                        "doi": paper.doi or "",
                        "arxiv_id": paper.arxiv_id or "",
                        "fallback_used": "true" if fallback_used else "false",
                        "web_supplement": (
                            "true" if provider_set.intersection(_WEB_PROVIDERS) else "false"
                        ),
                    },
                )
            )
        return candidates

    @staticmethod
    def _merge_papers(
        papers_by_id: dict[str, PaperRecord], incoming: list[PaperRecord]
    ) -> None:
        for paper in incoming:
            previous = papers_by_id.get(paper.paper_id)
            if previous is None:
                papers_by_id[paper.paper_id] = paper
                continue
            source_records = list(previous.source_records)
            for record in paper.source_records:
                if record not in source_records:
                    source_records.append(record)
            verification_status = previous.verification_status
            if verification_status != "verified" and paper.verification_status == "verified":
                verification_status = "verified"
            rank_features = previous.rank_features
            if (
                paper.rank_features is not None
                and (rank_features is None or paper.rank_features.score > rank_features.score)
            ):
                rank_features = paper.rank_features
            papers_by_id[paper.paper_id] = previous.model_copy(
                update={
                    "abstract": max(
                        (value for value in (previous.abstract, paper.abstract) if value),
                        key=len,
                        default=None,
                    ),
                    "urls": sorted(set(previous.urls) | set(paper.urls)),
                    "source_records": source_records,
                    "verification_status": verification_status,
                    "verification_methods": sorted(
                        set(previous.verification_methods) | set(paper.verification_methods)
                    ),
                    "matched_gap_ids": sorted(
                        set(previous.matched_gap_ids) | set(paper.matched_gap_ids)
                    ),
                    "rank_features": rank_features,
                }
            )

    @staticmethod
    def _source_kind(providers: set[str]) -> str:
        academic = bool(providers.intersection(_ACADEMIC_PROVIDERS))
        web = bool(providers.intersection(_WEB_PROVIDERS))
        if academic and web:
            return "academic+web"
        if web:
            return "web"
        return "academic"

    def last_provider_results(self, query_id: str) -> list[ProviderResult]:
        return list(self._last_results.get(query_id, []))

    def last_query_diagnostics(self, query_id: str) -> dict[str, object]:
        results = self._last_results.get(query_id, [])
        return {
            "query_id": query_id,
            "fallback_used": self._last_fallback_used.get(query_id, False),
            "provider_statuses": [
                {
                    "provider": result.provider,
                    "status": result.status,
                    "error_code": result.error_code,
                }
                for result in results
            ],
        }

    @staticmethod
    def _build_plan(
        query: SearchQuery,
        source_preferences: list[str],
        *,
        lane_suffix: str,
    ) -> LiteratureQueryPlan:
        lane = QueryLane(
            lane_id=f"{query.query_id}-{lane_suffix}",
            purpose="method",
            query=query.query,
            source_preferences=list(source_preferences),
            gap_ids=[query.gap_id],
            priority=80,
        )
        return LiteratureQueryPlan(
            question=query.query,
            scope="literature retrieval",
            query_lanes=[lane],
            required_gap_ids=[query.gap_id],
            max_rounds=1,
        )

    @staticmethod
    def _locator(doi: str | None, arxiv_id: str | None, urls: list[str]) -> str:
        if doi:
            return f"doi:{doi}"
        if arxiv_id:
            return f"https://arxiv.org/abs/{arxiv_id}"
        if urls:
            return urls[0]
        return "literature://pending"
