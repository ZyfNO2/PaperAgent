from __future__ import annotations

import re
from collections.abc import Iterable
from hashlib import sha256

from paperagent.errors import ProviderError
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.literature.source_policy import SearchSourcePolicy, review_search_query
from paperagent.schemas import SearchCandidate, SearchQuery
from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    PaperRecord,
    ProviderResult,
    QueryLane,
    QueryPurpose,
)

_ACADEMIC_PROVIDERS = frozenset({"openalex", "semantic_scholar", "arxiv"})
_WEB_PROVIDERS = frozenset({"tavily", "duckduckgo"})


_GITHUB_REPOSITORY_URL = re.compile(
    r"https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_REPOSITORY_RELATION_CUES = (
    "code",
    "implementation",
    "repository",
    "source",
    "available at",
    "released at",
    "github",
)


def _normalized_github_repository_urls(paper: PaperRecord) -> list[tuple[str, str]]:
    text = "\n".join([paper.abstract or "", *paper.urls])
    repositories: dict[str, str] = {}
    for match in _GITHUB_REPOSITORY_URL.finditer(text):
        owner = match.group("owner")
        repo = match.group("repo").rstrip(".,;:)]}")
        if repo.casefold().endswith(".git"):
            repo = repo[:-4]
        if not owner or not repo:
            continue
        title = f"{owner}/{repo}"
        url = f"https://github.com/{title}"
        context_start = max(0, match.start() - 100)
        context_end = min(len(text), match.end() + 100)
        context = text[context_start:context_end].casefold()
        if not any(cue in context for cue in _REPOSITORY_RELATION_CUES):
            continue
        repositories[url.casefold()] = title
    return [(url, title) for url, title in sorted(repositories.items())]


_QUOTED_TITLE = re.compile(r'["“](?P<title>[^"”]{8,})["”]')
_DATASET_CONTEXT = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z0-9._-]{2,})\s+(?:dataset|benchmark|corpus)\b",
    re.IGNORECASE,
)
_DATASET_GENERIC = frozenset(
    {
        "audio",
        "public",
        "training",
        "test",
        "evaluation",
        "forecasting",
        "anomaly",
        "detection",
        "classification",
        "dataset",
        "benchmark",
        "corpus",
        "available",
        "specific",
        "large-scale",
        "self-built",
        "latest",
        "this",
        "that",
        "image",
        "images",
        "challenge",
    }
)
_DATASET_MODEL_TOKENS = frozenset(
    {
        "bert",
        "cnn",
        "detr",
        "gat",
        "gcn",
        "gnn",
        "gru",
        "llm",
        "lora",
        "lstm",
        "mlp",
        "rnn",
        "transformer",
        "vit",
        "yolo",
    }
)


def _quoted_title(query: str) -> str | None:
    match = _QUOTED_TITLE.search(query)
    if match is None:
        return None
    title = match.group("title").strip()
    return title or None


def _identity_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _exact_title_match(left: str, right: str) -> bool:
    left_tokens = _identity_tokens(left)
    right_tokens = _identity_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if len(left_tokens) == 1 and len(left_tokens[0]) >= 3 and left_tokens[0] == right_tokens[0]:
        return True
    if len(right_tokens) == 1 and len(right_tokens[0]) >= 3 and right_tokens[0] == left_tokens[0]:
        return True
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    overlap = left_set & right_set
    union = left_set | right_set
    length_ratio = min(len(left_set), len(right_set)) / max(len(left_set), len(right_set))
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.9 and length_ratio >= 0.8


def _looks_like_dataset_name(value: str) -> bool:
    name = value.strip(".,;:()[]{}")
    normalized = name.casefold()
    compact = re.sub(r"[^A-Za-z0-9]", "", name)
    if (
        len(compact) < 3
        or len(compact) > 40
        or normalized in _DATASET_GENERIC
        or normalized in _DATASET_MODEL_TOKENS
    ):
        return False
    if any(char.isdigit() for char in compact):
        return True
    if compact.isupper():
        return True
    return any(char.isupper() for char in compact[1:]) and any(char.islower() for char in compact)


def _explicit_dataset_names_from_text(text: str) -> tuple[str, ...]:
    names: list[str] = []
    context = re.compile(
        r"(?P<names>[A-Za-z][A-Za-z0-9._-]*(?:\s*(?:/|,|and)\s*"
        r"[A-Za-z][A-Za-z0-9._-]*)*)\s+(?:datasets?|benchmarks?|corpus|corpora)\b",
        re.IGNORECASE,
    )
    for match in context.finditer(text):
        for raw_name in re.split(r"\s*(?:/|,|and)\s*", match.group("names")):
            name = raw_name.strip(".,;:()[]{}")
            if _looks_like_dataset_name(name) and name not in names:
                names.append(name)
    return tuple(names)


def _distinctive_dataset_tokens(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9._-]{2,}\b", text):
        name = token.strip(".,;:()[]{}")
        if _looks_like_dataset_name(name) and name not in names:
            names.append(name)
    return tuple(names)


def _dataset_names_from_text(text: str) -> tuple[str, ...]:
    return _explicit_dataset_names_from_text(text)


def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    names = list(_explicit_dataset_names_from_text(query))
    for name in _distinctive_dataset_tokens(query):
        if name not in names:
            names.append(name)
    return tuple(names)


def _paper_dataset_mentions(query: str, paper: PaperRecord) -> tuple[str, ...]:
    paper_text = f"{paper.canonical_title}\n{paper.abstract or ''}"
    normalized = paper_text.casefold()
    names = list(_explicit_dataset_names_from_text(paper_text))
    for name in _explicit_dataset_names_from_text(query):
        if name.casefold() in normalized and name not in names:
            names.append(name)
    return tuple(names)


def _dataset_relation_names(
    query: str,
    papers: Iterable[PaperRecord],
) -> tuple[str, ...]:
    paper_list = tuple(papers)
    blocked = {
        token.casefold()
        for paper in paper_list
        for token in _distinctive_dataset_tokens(paper.canonical_title)
    }
    names = [name for name in _dataset_names_from_query(query) if name.casefold() not in blocked]
    for paper in paper_list:
        for name in _explicit_dataset_names_from_text(
            f"{paper.canonical_title}\n{paper.abstract or ''}"
        ):
            if name not in names:
                names.append(name)
    return tuple(names)


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
        academic = [*(source_preferences or ["openalex", "semantic_scholar", "arxiv"])]
        academic.extend(supplement_source_preferences or [])
        self._academic_sources = tuple(dict.fromkeys(academic))
        self._web_sources = tuple(dict.fromkeys(fallback_source_preferences or []))
        self._last_results: dict[str, list[ProviderResult]] = {}
        self._last_fallback_used: dict[str, bool] = {}
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
        required_title = _quoted_title(query.query)
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

        available = set(self._service.provider_names)
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
        relation_paper_ids: set[str] = set()
        dataset_links: dict[str, set[str]] = {}

        for provider_name in academic_order:
            if len(attempted) >= policy.maximum_provider_calls:
                break
            bundle = await self._service.retrieve(
                self._build_plan(
                    query,
                    [provider_name],
                    lane_suffix=provider_name,
                    query_text=required_title or query.query,
                    purpose="baseline" if required_title is not None else "method",
                    priority=95 if required_title is not None else 80,
                )
            )
            attempted.append(provider_name)
            provider_results.extend(bundle.provider_results)
            self._merge_papers(papers_by_id, bundle.papers)
            if self._has_sufficient_academic_evidence(
                papers_by_id.values(), policy, required_title=required_title
            ):
                stop_reason = "sufficient_academic_evidence"
                break

        relation_names = (
            _dataset_relation_names(query.query, papers_by_id.values())
            if "dataset" in query.source_types
            else ()
        )
        if relation_names and len(attempted) < policy.maximum_provider_calls:
            dataset_name = relation_names[0]
            relation_query = f'"{dataset_name}" dataset benchmark baseline method comparison'
            for relation_provider in self._relation_providers(academic_order):
                if len(attempted) >= policy.maximum_provider_calls:
                    break
                bundle = await self._service.retrieve(
                    self._build_plan(
                        query,
                        [relation_provider],
                        lane_suffix=(f"dataset-{dataset_name.casefold()}-{relation_provider}"),
                        query_text=relation_query,
                        purpose="benchmark_dataset",
                        priority=75,
                    )
                )
                attempted.append(f"{relation_provider}:dataset_relation")
                provider_results.extend(bundle.provider_results)
                relation_found = False
                for paper in bundle.papers:
                    if self._passes_relation_relevance(
                        paper,
                        dataset_name=dataset_name,
                    ):
                        relation_found = True
                        relation_paper_ids.add(paper.paper_id)
                        dataset_links.setdefault(paper.paper_id, set()).add(dataset_name)
                self._merge_papers(papers_by_id, bundle.papers)
                if relation_found:
                    break

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
                "all attempted literature providers failed",
                provider=self.provider_name,
                task=query.query_id,
                retryable=True,
                code="ALL_LITERATURE_PROVIDERS_FAILED",
            )

        filtered = [
            paper
            for paper in papers_by_id.values()
            if self._passes_return_relevance(paper, policy) or paper.paper_id in relation_paper_ids
        ]
        if required_title is not None:
            filtered = [
                paper
                for paper in filtered
                if _exact_title_match(paper.canonical_title, required_title)
                or paper.paper_id in relation_paper_ids
            ]
        filtered.sort(
            key=lambda paper: (
                int(
                    required_title is not None
                    and _exact_title_match(paper.canonical_title, required_title)
                ),
                int(paper.paper_id in relation_paper_ids),
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
        candidates: list[SearchCandidate] = []
        for paper in selected:
            relation = (
                "declared_identity"
                if required_title is not None
                and _exact_title_match(paper.canonical_title, required_title)
                else (
                    "parallel_via_dataset"
                    if paper.paper_id in relation_paper_ids
                    else "direct_query"
                )
            )
            candidates.extend(
                self._candidates(
                    query,
                    paper,
                    fallback_used,
                    relation=relation,
                    linked_dataset_names=tuple(sorted(dataset_links.get(paper.paper_id, set()))),
                )
            )
        return candidates

    def _academic_order(self, policy: SearchSourcePolicy, available: set[str]) -> tuple[str, ...]:
        policy_order = (policy.primary_provider, *policy.escalation_providers)
        allowed = set(self._academic_sources).intersection(_ACADEMIC_PROVIDERS)
        return tuple(
            provider
            for provider in dict.fromkeys(policy_order)
            if provider in available and provider in allowed
        )

    @staticmethod
    def _relation_providers(academic_order: tuple[str, ...]) -> tuple[str, ...]:
        preferred_order = ("openalex", "arxiv", "semantic_scholar")
        return tuple(provider for provider in preferred_order if provider in academic_order)

    @staticmethod
    def _has_sufficient_academic_evidence(
        papers: Iterable[PaperRecord],
        policy: SearchSourcePolicy,
        *,
        required_title: str | None = None,
    ) -> bool:
        paper_list = list(papers)
        if required_title is not None:
            return any(
                paper.verification_status == "verified"
                and _exact_title_match(paper.canonical_title, required_title)
                for paper in paper_list
            )
        relevant = sum(
            paper.verification_status == "verified"
            and paper.rank_features is not None
            and paper.rank_features.relevance >= policy.minimum_relevance
            and paper.rank_features.score >= policy.minimum_rank_score
            for paper in paper_list
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

    @staticmethod
    def _passes_relation_relevance(
        paper: PaperRecord,
        *,
        dataset_name: str,
    ) -> bool:
        if paper.verification_status != "verified":
            return False
        text = f"{paper.canonical_title}\n{paper.abstract or ''}".casefold()
        if dataset_name.casefold() in text:
            return True
        features = paper.rank_features
        return features is not None and features.relevance >= 0.32 and features.score >= 0.55

    def _candidates(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
        *,
        relation: str = "direct_query",
        linked_dataset_names: tuple[str, ...] = (),
    ) -> list[SearchCandidate]:
        candidates = [self._candidate(query, paper, fallback_used, relation=relation)]
        if paper.verification_status != "verified":
            return candidates
        providers = sorted({record.provider for record in paper.source_records})
        score = paper.rank_features.score if paper.rank_features else 0.0
        relevance = paper.rank_features.relevance if paper.rank_features else 0.0
        if {"repository", "web"}.intersection(query.source_types):
            for url, title in _normalized_github_repository_urls(paper):
                digest = sha256(url.casefold().encode("utf-8")).hexdigest()[:20]
                candidates.append(
                    SearchCandidate(
                        candidate_id=f"repository-{digest}",
                        query_id=query.query_id,
                        gap_id=query.gap_id,
                        source_type="repository",
                        title=title,
                        locator=url,
                        snippet=(
                            f"Repository explicitly linked from the verified paper "
                            f"{paper.canonical_title!r}. The paper text or provider metadata "
                            f"contains the repository URL {url}."
                        ),
                        provider=self.provider_name,
                        metadata={
                            "query_text": query.query,
                            "verification_status": "verified",
                            "providers": ",".join(providers),
                            "provider_classes": "academic-linked-repository",
                            "source_kind": "repository",
                            "rank_score": f"{score:.6f}",
                            "relevance_score": f"{relevance:.6f}",
                            "relation": "author_linked_from_verified_paper",
                            "parent_paper_id": paper.paper_id,
                            "parent_paper_title": paper.canonical_title,
                            "repository_ref": url,
                            "fallback_used": "true" if fallback_used else "false",
                            "web_supplement": "false",
                        },
                    )
                )
        if "dataset" in query.source_types:
            parent_locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
            explicit_mentions = _paper_dataset_mentions(query.query, paper)
            dataset_names = list(explicit_mentions)
            for linked_name in linked_dataset_names:
                if linked_name not in dataset_names:
                    dataset_names.append(linked_name)
            for dataset_name in dataset_names:
                identity = f"{dataset_name.casefold()}|{paper.paper_id}"
                digest = sha256(identity.encode("utf-8")).hexdigest()[:20]
                explicitly_named = dataset_name in explicit_mentions
                dataset_relation = (
                    "dataset_named_in_verified_paper"
                    if explicitly_named
                    else "dataset_linked_by_focused_retrieval"
                )
                snippet = (
                    f"Dataset {dataset_name!r} is explicitly named in the title or abstract "
                    f"of the verified paper {paper.canonical_title!r}. This verifies the "
                    "dataset mention, not an official download page or split manifest."
                    if explicitly_named
                    else (
                        f"Dataset {dataset_name!r} was the explicit anchor of a focused academic "
                        f"retrieval that returned verified paper {paper.canonical_title!r}. "
                        "This is a paper-dataset relation for discovery, not verification of an "
                        "official download page, license, or split manifest."
                    )
                )
                candidates.append(
                    SearchCandidate(
                        candidate_id=f"dataset-{digest}",
                        query_id=query.query_id,
                        gap_id=query.gap_id,
                        source_type="dataset",
                        title=dataset_name,
                        locator=parent_locator,
                        snippet=snippet,
                        provider=self.provider_name,
                        metadata={
                            "query_text": query.query,
                            "verification_status": "verified",
                            "verification_scope": (
                                "paper_mention" if explicitly_named else "retrieval_relation"
                            ),
                            "providers": ",".join(providers),
                            "provider_classes": "academic-linked-dataset-relation",
                            "source_kind": "dataset",
                            "rank_score": f"{score:.6f}",
                            "relevance_score": f"{relevance:.6f}",
                            "relation": dataset_relation,
                            "parent_paper_id": paper.paper_id,
                            "parent_paper_title": paper.canonical_title,
                            "dataset_ref": dataset_name,
                            "fallback_used": "true" if fallback_used else "false",
                            "web_supplement": "false",
                        },
                    )
                )
        return candidates

    def _candidate(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
        *,
        relation: str = "direct_query",
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
                "query_text": query.query,
                "verification_status": paper.verification_status,
                "providers": ",".join(providers),
                "provider_classes": source_kind,
                "source_kind": source_kind,
                "relation": relation,
                "baseline_candidate": (
                    "declared" if relation == "declared_identity" else "inferred"
                ),
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
        query_text: str | None = None,
        purpose: QueryPurpose = "method",
        priority: int = 80,
    ) -> LiteratureQueryPlan:
        effective_query = query_text or query.query
        lane = QueryLane(
            lane_id=f"{query.query_id}-{lane_suffix}",
            purpose=purpose,
            query=effective_query,
            source_preferences=list(source_preferences),
            gap_ids=[query.gap_id],
            priority=priority,
        )
        return LiteratureQueryPlan(
            question=effective_query,
            scope="literature retrieval and bounded evidence relation expansion",
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
