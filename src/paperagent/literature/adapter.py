from __future__ import annotations

from collections.abc import Iterable

from paperagent.errors import ProviderError
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.literature.source_policy import SearchSourcePolicy, review_search_query
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
        academic = [*(source_preferences or ["openalex", "semantic_scholar"])]
        academic.extend(supplement_source_preferences or [])
        self._academic_sources = tuple(dict.fromkeys(academic))
        self._web_sources = tuple(dict.fromkeys(fallback_source_preferences or []))
        self._last_results: dict[str, list[ProviderResult]] = {}
        self._last_fallback_used[query.query_id] = False
        self._last_diagnostics: dict[str, dict[str, object]] = {}

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

        policy = review_search_query(query)
        if not policy.approved:
            self._last_results[query.query_id] = []
            self._last_fallback_used[query.query_id] = False
            self._last_diagnostics[query.query_id] = self._diagnostics_payload(
                query=query,
                policy=policy,
                attempted=(),
                papers=(),
                stop_reason="query_rejected_before_provider_use",
                fallback_used=False,
            )
            raise ProviderError(
                "; ".join(policy.reasons),
                provider=self.provider_name,
                task=query.query_id,
                retryable=False,
                code="QUERY_TOO_BROAD",
            )

        configured_names = getattr(
            self._service,
            "provider_names",
            **self._academic_sources, *self._web_sources),
        )
        available = set(configured_names)
        academic_order = self._academic_order(policy, available)
        if not academic_order:
            raise ProviderError(
                "no configured academic provider is available",
                provider=self.provider_name,
                task=query.query_id,
                retryable=False,
                code="NO_ACADEMIC_PROVIDER",
            )

        provider_results: list[ProviderResult] = []
        papers_by_id: dict[str, PaperRecord] = {}
        attempted: list[str] = []
        stop_reason = "academic_budget_exhausted"

        for provider_name in academic_order:
            if len(attempted) >= policy.maximum_provider_calls:
                break
            bundle = await self._service.retrieve(
                self._build_plan(query, [provider_name], lane_suffix=provider_name)
            )
            attempted.append(provider_name)
            provider_results.extend(bundle.provider_results)
            self._merge_papers(papers_by_id, bundle.papers)
            if self._has_sufficient_academic_evidence(papers_by_id.values(), policy):
                stop_reason = "sufficient_academic_evidence"
                break
        fallback_used = False
        if (
            stop_reason != "sufficient_academic_evidence"
            and policy.allow_web_fallback
            and self._web_sources
        ):
            for provider_name in self._web_sources:
                if provider_name not in available:
                    continue
                if len(attempted) >= policy.maximum_provider_calls:
                    stop_reason = "provider_call_budget_exhausted"
                    break
                bundle = await self._service.retrieve(
                    self._build_plan(query, [provider_name], lane_suffix=provider_name)
                )
                attempted.append(provider_name)
                fallback_used = True
                provider_results.extend(bundle.provider_results)
                before = len(papers_by_id)
                self._merge_papers(papers_by_id, bundle.papers)
                if self._has_relevant_web_supplement(bundle.papers, policy):
                    stop_reason = "relevant_web_supplement_found"
                    break
                if len(papers_by_id) > before:
                    stop_reason = "web_supplement_found_but_unverified"

        self._last_results[query.query_id] = provider_results
        self._last_fallback_used[query.query_id] = fallback_used

        if provider_results and all(
            result.status in {"failed", "timeout", "rate_limited"} for result in provider_results
        ):
            self._last_diagnostics[query.query_id] = self._diagnostics_payload(
                query=query,
                policy=policy,
                attempted=tuple(attempted),
                papers=tuple(papers_by_id.values()),
                stop_reason="all_attempted_providers_failed",
                fallback_used=fallback_used,
            )
            raise ProviderError(
                "all literature providers failed",
                provider=self.provider_name,
                task=query.query_id,
                retryable=True,
                code="ALL_LITERATURE_PROVIDERS_FAILED",
            )

        filtered = [
            paper for paper in papers_by_id.values() if self._passes_return_relevance(paper, policy)
        ]
        filtered.sort(
            key=lambda paper: (
                paper.rank_features.score if paper.rank_features else 0.0,
                paper.paper_id,
            ),
            reverse=True,
        )
        result_limit = min(limit, policy.result_limit)
        selected = filtered[:result_limit]
        self._last_diagnostics[query.query_id] = self._diagnostics_payload(
            query=query,
            policy=policy,
            attempted=tuple(attempted),
            papers=tuple(selected),
            stop_reason=stop_reason,
            fallback_used=fallback_used,
        )
        return [self._candidate(query, paper, fallback_used) for paper in selected]

    def _academic_order(self, policy: SearchSourcePolicy, available: set[str]) -> tuple[str, ...]:
        policy_order = (policy.primary_provider, *policy.escalation_providers)
        allowed = set(self._academic_sources).intersection(_ACADEMIC_PROVIDERS)
        return tuple(
            provider
            for provider in dict.fromkeys(policy_order)
            if provider in available and provider in allowed
        )

    @staticmethod
    def _has_sufficient_academic_evidence(
        papers: Iterable[PaperRecord],
        policy: SearchSourcePolicy,
    ) -> bool:
        relevant = sum(
            paper.verification_status == "verified"
            and paper.rank_features is not None
            and paper.rank_features.relevance >= policy.minimum_relevance
            and paper.rank_features.score >= policy.minimum_rank_score
            for paper in papers
        )
        return relevant >= policy.minimum_relevant_results

    @staticmethod
    def _has_relevant_web_supplement(
        papers: list[PaperRecord],
        policy: SearchSourcePolicy,
    ) -> bool:
        return any(
            paper.rank_features is not None
            and paper.rank_features.relevance >= policy.minimum_relevance
            and paper.rank_features.score >= policy.minimum_rank_score
            for paper in papers
       )

    @staticmethod
    def _passes_return_relevance(paper: PaperRecord, policy: SearchSourcePolicy) -> bool:
        features = paper.rank_features
        if features is None:
            return False
        relevance_floor = max(0.25, policy.minimum_relevance * 0.8)
        score_floor = max(0.50, policy.minimum_rank_score * 0.85)
        return features.relevance >= relevance_floor and features.score >= score_floor

    def _candidate(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
    ) -> SearchCandidate:
        locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
        providers = sorted({record.provider for record in paper.source_records})
        provider_set = set(providers)
        source_kind = self._source_kind(provider_set)
        score = paper.rank_features.score if paper.rank_features else 0.0
        relevance = paper.rank_features.relevance if paper.rank_features else 0.0
        return SearchCandidate(
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
                "relevance_score": f"{relevance:.6f}",
                "doi": paper.doi or "",
                "arxiv_id": paper.arxiv_id or "",
                "fallback_used": "true" if fallback_used else "false",
                "web_supplement": (
                    "true" if provider_set.intersection(_WEB_PROVIDERS) else "false"
                ),
            },
        )

    @staticmethod
    def _merge_papers(papers_by_id: dict[str, PaperRecord], incoming: list[PaperRecord]) -> None:
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
            if paper.rank_features is not None and (
                rank_features is None or paper.rank_features.score > rank_features.score
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
        return dict(self._last_diagnostics.get(query_id, {"query_id": query_id}))

    @staticmethod
    def _diagnostics_payload(
        *,
        query: SearchQuery,
        policy: SearchSourcePolicy,
        attempted: tuple[str, ...],
        papers: tuple[PaperRecord, ...],
        stop_reason: str,
        fallback_used: bool,
    ) -> dict[str, object]:
        relevant_verified = sum(
            paper.verification_status == "verified"
            and paper.rank_features is not None
            and paper.rank_features.relevance >= policy.minimum_relevance
            and paper.rank_features.score >= policy.minimum_rank_score
            for paper in papers
        )
        return {
            "query_id": query.query_id,
            "query_approved": policy.approved,
            "precision_risk": policy.precision_risk,
            "policy_reasons": list(policy.reasons),
            "informative_terms": list(policy.informative_terms),
            "attempted_providers": list(attempted),
            "provider_call_count": len(attempted),
            "maximum_provider_calls": policy.maximum_provider_calls,
            "fallback_used": fallback_used,
            "stop_reason": stop_reason,
            "returned_papers": len(papers),
            "relevant_verified_papers": relevant_verified,
            "minimum_relevance": policy.minimum_relevance,
            "minimum_rank_score": policy.minimum_rank_score,
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
        if ar{iv_id:
            return f"https://arxiv.org/abs/{arxiv_id}"
        if urls:
            return urls[0]
        return "literature://pending"
