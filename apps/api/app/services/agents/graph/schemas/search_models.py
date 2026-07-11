"""Re5.X: Pydantic models for search pipeline structured outputs.

SearchCard, SourceResult, Diagnosis, Observation — all LLM and adapter outputs
must pass through these models. Invalid/incomplete outputs are rejected, not
silently normalized.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any


class SourceResult(BaseModel):
    """Structured result from an adapter call.

    Replaces the pattern of returning [] for both 'empty' and 'failure'.
    """
    source: str = Field(description="Adapter name (arxiv, openalex, etc.)")
    query: str
    status: str = Field(description="success | empty | failed | rate_limited | disabled")
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    n_raw: int = 0

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        valid = {"success", "empty", "failed", "rate_limited", "disabled"}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}, got '{v}'")
        return v

    @property
    def is_empty_not_failed(self) -> bool:
        """True if query returned no results but source is still usable."""
        return self.status == "empty"


class SearchCard(BaseModel):
    """A single search query targeting a specific evidence role."""
    card_id: str = Field(description="Unique ID, e.g. 'sc-001'")
    source: str = Field(description="Must be from allowed_sources")
    query: str = Field(min_length=2, description="Search query text")
    target_role: str = Field(
        default="core",
        description="core | baseline | parallel | dataset | repo | metadata"
    )
    expected_signal: str | None = None
    query_term_origin: list[dict[str, str]] = Field(default_factory=list)
    stop_if: str | None = None

    @field_validator("target_role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        valid = {"core", "baseline", "parallel", "dataset", "repo", "metadata"}
        if v not in valid:
            raise ValueError(f"target_role must be one of {valid}")
        return v


class Diagnosis(BaseModel):
    """Reflection critic's diagnosis of the previous search round."""
    diagnosis_id: str
    diagnosis_code: str = Field(
        description="role_gap | low_precision | query_too_narrow | query_too_broad | "
                    "source_unavailable | metadata_gap | no_repair_route | unknown"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    action: str = Field(
        description="rewrite_query | switch_source | expand_from_accepted_seed | "
                    "repair_metadata | stop_with_explicit_gap"
    )
    target_role: str | None = None
    evidence_ids: list[str] = Field(
        description="Must reference observation query_ids or candidate_ids; cannot be empty"
    )
    must_keep_terms: list[str] = Field(default_factory=list)
    avoid_terms: list[str] = Field(default_factory=list)
    source_preference: list[str] = Field(default_factory=list)
    stop_reason: str | None = None

    @field_validator("evidence_ids")
    @classmethod
    def _nonempty_evidence(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("evidence_ids cannot be empty — must reference observations")
        return v

    @field_validator("diagnosis_code")
    @classmethod
    def _valid_code(cls, v: str) -> str:
        valid = {"role_gap", "low_precision", "query_too_narrow", "query_too_broad",
                 "source_unavailable", "metadata_gap", "no_repair_route", "unknown"}
        if v not in valid:
            raise ValueError(f"diagnosis_code must be one of {valid}")
        return v

    @field_validator("action")
    @classmethod
    def _valid_action(cls, v: str) -> str:
        valid = {"rewrite_query", "switch_source", "expand_from_accepted_seed",
                 "repair_metadata", "stop_with_explicit_gap"}
        if v not in valid:
            raise ValueError(f"action must be one of {valid}")
        return v


class Observation(BaseModel):
    """Aggregated observation from a search round, fed to reflection."""
    round: int
    card_id: str
    source: str
    query: str
    source_status: str
    n_raw: int = 0
    n_relevant: int = 0
    n_verified: int = 0
    candidate_ids: list[str] = Field(default_factory=list)
    rejected_titles: list[str] = Field(default_factory=list)

    @field_validator("source_status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        valid = {"success", "empty", "failed", "rate_limited", "disabled"}
        if v not in valid:
            raise ValueError(f"source_status must be one of {valid}")
        return v


class CoverageGate(BaseModel):
    """Result of coverage gate check."""
    required_roles: dict[str, int] = Field(description="role → required count")
    optional_roles: dict[str, int] = Field(default_factory=dict)
    current_coverage: dict[str, int] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    budget_remaining: int = 0
    decision: str = Field(description="pass | reflect | stop_with_gap")

    @field_validator("decision")
    @classmethod
    def _valid_decision(cls, v: str) -> str:
        valid = {"pass", "reflect", "stop_with_gap"}
        if v not in valid:
            raise ValueError(f"decision must be one of {valid}")
        return v
