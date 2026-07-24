from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel

ProviderStatus = Literal["success", "empty", "rate_limited", "timeout", "failed"]
CacheStatus = Literal["miss", "hit", "coalesced", "bypass"]
VerificationStatus = Literal["verified", "pending", "suspicious", "failed", "rejected"]
QueryPurpose = Literal[
    "baseline",
    "method",
    "benchmark_dataset",
    "evaluation_metric",
    "limitation_failure",
    "recent_progress",
    "contradictory_evidence",
]
RetryRecommendation = Literal["none", "focused_retry", "budget_exhausted", "blocked"]


class LiteratureFilters(FrozenModel):
    year_min: int | None = Field(default=None, ge=1000, le=3000)
    year_max: int | None = Field(default=None, ge=1000, le=3000)
    languages: list[str] = Field(default_factory=list)
    publication_types: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_year_range(self) -> LiteratureFilters:
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min cannot exceed year_max")
        return self


class QueryLane(FrozenModel):
    lane_id: str = Field(min_length=1)
    purpose: QueryPurpose
    query: str = Field(min_length=2)
    source_preferences: list[str] = Field(default_factory=list)
    gap_ids: list[str] = Field(min_length=1)
    priority: int = Field(default=50, ge=0, le=100)


class LiteratureQueryPlan(FrozenModel):
    schema_version: Literal["0.2"] = "0.2"
    question: str = Field(min_length=3)
    scope: str = Field(min_length=1)
    query_lanes: list[QueryLane] = Field(min_length=1, max_length=4)
    required_gap_ids: list[str] = Field(min_length=1)
    filters: LiteratureFilters = Field(default_factory=LiteratureFilters)
    max_rounds: int = Field(default=2, ge=1, le=2)

    @model_validator(mode="after")
    def validate_gaps(self) -> LiteratureQueryPlan:
        known = {gap for lane in self.query_lanes for gap in lane.gap_ids}
        missing = set(self.required_gap_ids) - known
        if missing:
            raise ValueError(f"required gaps have no query lane: {sorted(missing)}")
        lane_ids = [lane.lane_id for lane in self.query_lanes]
        if len(lane_ids) != len(set(lane_ids)):
            raise ValueError("query lane IDs must be unique")
        return self


class ProviderPaper(FrozenModel):
    provider_record_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1000, le=3000)
    abstract: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    urls: list[str] = Field(default_factory=list)
    citation_count: int = Field(default=0, ge=0)
    publication_type: str | None = None
    language: str | None = None
    matched_gap_ids: list[str] = Field(default_factory=list)
    source_lane_ids: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResult(FrozenModel):
    provider: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    status: ProviderStatus
    papers: list[ProviderPaper] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime
    retry_count: int = Field(default=0, ge=0)
    cache_status: CacheStatus = "miss"
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> ProviderResult:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at cannot precede started_at")
        if self.status == "empty" and self.papers:
            raise ValueError("empty result cannot contain papers")
        if self.status in {"rate_limited", "timeout", "failed"} and self.papers:
            raise ValueError("failed provider result cannot contain papers")
        if self.status == "success" and not self.papers:
            raise ValueError("success result must contain at least one paper")
        if self.status in {"rate_limited", "timeout", "failed"} and not self.error_code:
            raise ValueError("failure result requires error_code")
        return self


class SourceRecord(FrozenModel):
    provider: str
    provider_record_id: str
    request_id: str


class MergeWarning(FrozenModel):
    code: str
    message: str
    providers: list[str] = Field(default_factory=list)


class RankFeatures(FrozenModel):
    relevance: float = Field(ge=0, le=1)
    gap_coverage: float = Field(ge=0, le=1)
    metadata_verification: float = Field(ge=0, le=1)
    recency_fit: float = Field(ge=0, le=1)
    diversity: float = Field(ge=0, le=1)
    citation_tiebreaker: float = Field(ge=0)
    score: float = Field(ge=0, le=1)
    explanation: list[str] = Field(default_factory=list)


class PaperRecord(FrozenModel):
    paper_id: str
    canonical_title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    urls: list[str] = Field(default_factory=list)
    source_records: list[SourceRecord] = Field(default_factory=list)
    verification_status: VerificationStatus = "pending"
    verification_methods: list[str] = Field(default_factory=list)
    matched_gap_ids: list[str] = Field(default_factory=list)
    rank_features: RankFeatures | None = None
    merge_warnings: list[MergeWarning] = Field(default_factory=list)
    citation_count: int = Field(default=0, ge=0)
    publication_type: str | None = None
    language: str | None = None


class CoverageReport(FrozenModel):
    gap_coverage: dict[str, int] = Field(default_factory=dict)
    uncovered_gap_ids: list[str] = Field(default_factory=list)
    source_diversity: int = Field(default=0, ge=0)
    publication_year_distribution: dict[str, int] = Field(default_factory=dict)
    verification_distribution: dict[str, int] = Field(default_factory=dict)
    retry_recommendation: RetryRecommendation = "none"
    warnings: list[str] = Field(default_factory=list)


class RetrievalMetrics(FrozenModel):
    rounds: int = Field(default=0, ge=0, le=2)
    provider_calls: int = Field(default=0, ge=0)
    query_rewrite_calls: int = Field(default=0, ge=0, le=1)
    cache_hits: int = Field(default=0, ge=0)


class LiteratureBundle(FrozenModel):
    papers: list[PaperRecord] = Field(default_factory=list, max_length=12)
    provider_results: list[ProviderResult] = Field(default_factory=list)
    coverage: CoverageReport
    metrics: RetrievalMetrics
