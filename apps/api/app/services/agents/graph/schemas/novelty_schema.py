"""Re6.4 Academic Tailor 2.0 — Novelty schemas.

EvidenceContext, NoveltyCandidate, DifferentiationMatrix, FalsifiableProposition,
ReviewerPressurePoint, ContributionProofPlan, NoveltyRevision.

Extends the existing evidence_schema.py with the P-M-I framework.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EvidenceContext(BaseModel):
    """A single piece of evidence backing a novelty claim."""
    candidate_id: str
    chunk_id: str | None = None
    snippet: str = ""
    location: str = ""
    role: Literal["problem", "method", "insight", "adjacent"] = "problem"
    source_quality: Literal["verified", "user_uploaded", "rag_extracted"] = "verified"


class NoveltyCandidate(BaseModel):
    """P-M-I structured novelty claim bound to evidence."""
    candidate_id: str = Field(default_factory=lambda: _uuid())
    problem: str = ""
    method: str = ""
    insight: str = ""
    scope: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal[
        "draft", "needs_evidence", "needs_rewrite",
        "under_review", "accepted", "rejected", "needs_literature_verification"
    ] = "draft"
    pseudo_innovation_risks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_evidence_binding(self) -> "NoveltyCandidate":
        if self.status in ("accepted", "under_review"):
            if len(self.evidence_ids) < 3:
                raise ValueError(
                    f"status={self.status} requires at least 3 evidence_ids "
                    f"(problem/method/insight), got {len(self.evidence_ids)}"
                )

        # Insight must not be a pure performance statement
        _perf_keywords = ("提高了", "提升了", "提升了", "准确率达到", "精度达到",
                          "F1 提高了", "精度提升了", "mAP", "accuracy", "F1 score",
                          "improves by", "achieves", "outperforms", "SOTA")
        insight_lower = self.insight.lower()
        perf_counts = sum(1 for kw in _perf_keywords if kw in insight_lower)
        if perf_counts >= 2 and "具体机制" not in self.insight:
            if self.status not in ("needs_evidence", "needs_rewrite", "rejected"):
                self.status = "needs_evidence"

        return self

    @model_validator(mode="after")
    def _validate_first_claim(self) -> "NoveltyCandidate":
        first_markers = ("first", "首次", "最先", "从未", "开创性", "首次提出",
                         "没有先例", "尚未有", "首例")
        if any(m in self.problem + self.method + self.insight for m in first_markers):
            if self.status not in ("needs_evidence", "needs_rewrite", "rejected",
                                    "needs_literature_verification"):
                self.status = "needs_literature_verification"
                self.pseudo_innovation_risks = list(set(
                    self.pseudo_innovation_risks + ["first_claim_unsupported"]
                ))
        return self

    def has_all_evidence_roles(self) -> bool:
        return len(self.evidence_ids) >= 3

    def is_insight_performance_only(self) -> bool:
        perf_indicators = ("提高了", "提升了", "outperforms", "achieves",
                           "SOTA", "state-of-the-art", "state of the art")
        return any(k in self.insight for k in perf_indicators) and len(self.insight) < 80


class DifferentiationMatrix(BaseModel):
    """How a novelty candidate differs from adjacent work in 5 dimensions."""
    adjacent_work_id: str = ""
    adjacent_work_label: str = ""
    problem_diff: str = ""
    method_diff: str = ""
    detail_diff: str = ""
    evidence_diff: str = ""
    insight_diff: str = ""

    @model_validator(mode="after")
    def _validate_all_dims(self) -> "DifferentiationMatrix":
        dims = ["problem_diff", "method_diff", "detail_diff", "evidence_diff", "insight_diff"]
        empty = [d for d in dims if not getattr(self, d, "").strip()]
        if empty:
            raise ValueError(f"differentiation matrix missing dimensions: {empty}")
        return self


class FalsifiableProposition(BaseModel):
    """A falsifiable proposition derived from an Insight."""
    proposition_id: str = Field(default_factory=lambda: _uuid())
    proposition: str = ""
    scoped_setting: str = ""
    observable_effect: str = ""
    support_condition: str = ""
    refute_condition: str = ""
    required_test: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["verified", "planned_not_verified", "refuted"] = "planned_not_verified"

    @model_validator(mode="after")
    def _validate_triad(self) -> "FalsifiableProposition":
        missing = []
        if not self.support_condition.strip():
            missing.append("support_condition")
        if not self.refute_condition.strip():
            missing.append("refute_condition")
        if not self.required_test.strip():
            missing.append("required_test")
        if missing:
            raise ValueError(
                f"falsifiable proposition missing: {missing}. "
                "All three (support/refute/required_test) are required."
            )
        return self


class ReviewerPressurePoint(BaseModel):
    """A reviewer pressure test point."""
    point_id: str = Field(default_factory=lambda: _uuid())
    risk: Literal["repetition", "motivation", "falsifiability", "differentiation", "story"] = "repetition"
    question: str = ""
    severity: Literal["high", "medium", "low"] = "medium"
    repair: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_evidence(self) -> "ReviewerPressurePoint":
        if not self.evidence_ids:
            self.evidence_ids = ["unknown"]
        return self


class ContributionProofPlan(BaseModel):
    """Plan for proving a contribution."""
    contribution: str = ""
    evidence_needed: list[str] = Field(default_factory=list)
    weakest_link: str = ""
    threshold: str = ""


class NoveltyRevision(BaseModel):
    """Append-only evolution log entry for a novelty candidate."""
    revision_id: str = Field(default_factory=lambda: _uuid())
    parent_revision_id: str | None = None
    version: int = 1
    candidate_id: str = ""  # Top-level reference for lookup
    reason: str = ""
    evidence_delta: list[str] = Field(default_factory=list)
    next_falsification_test: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    candidate_snapshot: NoveltyCandidate | None = None

    @model_validator(mode="after")
    def _validate_append_only(self) -> "NoveltyRevision":
        if self.parent_revision_id == self.revision_id:
            raise ValueError("revision cannot reference itself as parent")
        if self.candidate_snapshot and not self.candidate_id:
            self.candidate_id = self.candidate_snapshot.candidate_id
        return self


def _uuid() -> str:
    import uuid
    return uuid.uuid4().hex[:12]
