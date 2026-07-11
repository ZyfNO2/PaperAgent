"""Re4.3: Evidence-bound schemas for innovation, narrative, and work packages.

These Pydantic v2 models formalize the LLM output contracts that were
previously loose dicts. They enable:
  - Binding validators (Phase 2)
  - Devil's advocate evidence-level critique (Phase 4)
  - Stale marking on upstream changes (Phase 5)
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class EvidenceSnippet(BaseModel):
    """A snippet of evidence from a specific candidate paper."""
    candidate_id: str = Field(description="ID of the paper/repo this evidence comes from")
    snippet: str = Field(description="Verbatim or near-verbatim excerpt from the source")
    location: str | None = Field(default=None, description="Section/page/paragraph locator")
    verdict: str = Field(default="pending", description="pending | verified | rejected")


class InnovationPoint(BaseModel):
    """Innovation point with mandatory evidence binding."""
    description: str
    baseline_used: str | None = None
    stitched_modules: list[str] = Field(default_factory=list)
    stitching_plan: str | None = None
    estimated_difficulty: str | None = None
    evidence_ref: str | None = None

    candidate_ids: list[str] = Field(default_factory=list)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    novelty_score: float | None = Field(default=None, ge=0, le=10)
    feasibility_score: float | None = Field(default=None, ge=0, le=10)
    evidence_score: float | None = Field(default=None, ge=0, le=10)
    status: str = Field(default="pending", description="pending | verified | needs_evidence | rejected | stale")

    def has_evidence(self) -> bool:
        return bool(self.candidate_ids) or bool(self.evidence_snippets)


class StitchingPlan(BaseModel):
    """Structured stitching plan for innovation points."""
    baseline_model: str | None = None
    module_b: str | None = None
    module_c: str | None = None
    stitching_steps: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class NarrativeRevision(BaseModel):
    """One revision of the research narrative."""
    revision_id: str = Field(description="Unique ID, e.g. 'rev-0', 'rev-1'")
    parent_revision_id: str | None = Field(default=None)
    three_problems: list[dict[str, Any]] = Field(default_factory=list)
    nick_model_name: str | None = None
    narrative_summary: str | None = None
    chapter_outline: dict[str, Any] | None = None
    abstract_draft: str | None = None
    revision_reason: str | None = Field(default=None)
    revision_source: str = Field(default="initial")
    diff: dict[str, Any] | None = Field(default=None)


class WorkPackage(BaseModel):
    """Structured research work package with dependency tracking."""
    title: str
    research_question: str | None = None
    baseline: str | None = None
    improved_module_source: str | None = None
    data_source: str | None = None
    experiment_metrics: str | None = None
    risk: str | None = None
    estimated_workload: str | None = None

    objective: str | None = Field(default=None)
    method: str | None = Field(default=None)
    deliverable: str | None = Field(default=None)
    effort: str | None = Field(default=None)
    prerequisite_ids: list[str] = Field(default_factory=list)
    bound_candidate_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="pending")

    @property
    def package_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return f"wp-{slug[:30]}"


class BindingValidationResult(BaseModel):
    """Result of binding validation across innovation/narrative/work_package."""
    valid: bool
    issues: list[dict[str, Any]] = Field(default_factory=list)
    orphan_packages: list[str] = Field(default_factory=list)
    needs_evidence_items: list[str] = Field(default_factory=list)
    stale_items: list[str] = Field(default_factory=list)
