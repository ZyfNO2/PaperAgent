from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel

SourceType = Literal["paper", "dataset", "repository", "web", "user_material"]


def _default_source_types() -> list[SourceType]:
    return ["paper", "web"]


class EvidenceGap(FrozenModel):
    gap_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = True
    minimum_accepted_items: int = Field(default=1, ge=0, le=20)


class SearchQuery(FrozenModel):
    query_id: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    query: str = Field(min_length=2)
    source_types: list[SourceType] = Field(default_factory=_default_source_types)


class PreparedQuery(FrozenModel):
    query_id: str
    gap_id: str
    query: str
    original_query: str | None = None
    refinement_reason: str | None = None
    removed_families: list[str] = Field(default_factory=list)
    source_types: list[SourceType] = Field(default_factory=list)
    round: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_refinement_audit(self) -> PreparedQuery:
        changed = self.original_query is not None
        if changed:
            if not self.refinement_reason:
                raise ValueError("refined query requires refinement_reason")
            if not self.removed_families:
                raise ValueError("refined query requires removed_families")
            if self.original_query.strip() == self.query.strip():
                raise ValueError("refined query must differ from original_query")
        elif self.refinement_reason is not None or self.removed_families:
            raise ValueError("unmodified query cannot include refinement audit fields")
        return self


class ResearchPlan(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    status: Literal["ready", "need_human", "blocked"]
    problem_statement: str
    scope: str
    research_questions: list[str] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    search_queries: list[SearchQuery] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    block_reason: str | None = None

    @model_validator(mode="after")
    def validate_status_contract(self) -> ResearchPlan:
        if self.status == "ready":
            if not self.evidence_gaps or not self.search_queries:
                raise ValueError("ready plan requires at least one evidence gap and search query")
            known_gaps = {gap.gap_id for gap in self.evidence_gaps}
            unknown = {query.gap_id for query in self.search_queries} - known_gaps
            if unknown:
                raise ValueError(f"search queries reference unknown gaps: {sorted(unknown)}")
            if self.block_reason is not None:
                raise ValueError("ready plan cannot include block_reason")
        elif self.status == "need_human":
            if not self.clarification_question:
                raise ValueError("need_human plan requires clarification_question")
            if self.block_reason is not None:
                raise ValueError("need_human plan cannot include block_reason")
        elif self.status == "blocked":
            if not self.block_reason:
                raise ValueError("blocked plan requires block_reason")
            if self.clarification_question is not None:
                raise ValueError("blocked plan cannot include clarification_question")
        return self

    def validate_query_budget(self, maximum: int) -> None:
        if len(self.search_queries) > maximum:
            raise ValueError(f"query count {len(self.search_queries)} exceeds budget {maximum}")
