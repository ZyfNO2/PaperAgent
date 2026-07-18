from __future__ import annotations

from paperagent.errors import ProviderError
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.schemas import SearchCandidate, SearchQuery
from paperagent.schemas.literature import LiteratureQueryPlan, ProviderResult, QueryLane


class LiteratureSearchAdapter:
    provider_name = "literature_retrieval"

    def __init__(
        self,
        *,
        service: LiteratureRetrievalService,
        source_preferences: list[str] | None = None,
    ) -> None:
        self._service = service
        self._source_preferences = source_preferences or ["openalex", "semantic_scholar"]
        self._last_results: dict[str, list[ProviderResult]] = {}

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
        lane = QueryLane(
            lane_id=query.query_id,
            purpose="method",
            query=query.query,
            source_preferences=list(self._source_preferences),
            gap_ids=[query.gap_id],
            priority=80,
        )
        plan = LiteratureQueryPlan(
            question=query.query,
            scope="literature retrieval",
            query_lanes=[lane],
            required_gap_ids=[query.gap_id],
            max_rounds=1,
        )
        bundle = await self._service.retrieve(plan)
        self._last_results[query.query_id] = list(bundle.provider_results)
        if bundle.provider_results and all(
            result.status in {"failed", "timeout", "rate_limited"}
            for result in bundle.provider_results
        ):
            raise ProviderError(
                "all literature providers failed",
                provider=self.provider_name,
                task=query.query_id,
                retryable=True,
                code="ALL_LITERATURE_PROVIDERS_FAILED",
            )
        candidates: list[SearchCandidate] = []
        for paper in bundle.papers[:limit]:
            locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
            providers = sorted({record.provider for record in paper.source_records})
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
                        "rank_score": f"{score:.6f}",
                        "doi": paper.doi or "",
                        "arxiv_id": paper.arxiv_id or "",
                    },
                )
            )
        return candidates

    def last_provider_results(self, query_id: str) -> list[ProviderResult]:
        return list(self._last_results.get(query_id, []))

    @staticmethod
    def _locator(doi: str | None, arxiv_id: str | None, urls: list[str]) -> str:
        if doi:
            return f"doi:{doi}"
        if arxiv_id:
            return f"https://arxiv.org/abs/{arxiv_id}"
        if urls:
            return urls[0]
        return "literature://pending"
