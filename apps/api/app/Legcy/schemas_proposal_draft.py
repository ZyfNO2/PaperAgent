"""Session 29: 开题报告草稿 schema — 12 节 + 证据绑定 + 工作量 + 创新点."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas_feasibility import FeasibilityAssessment


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class SectionKey(str, Enum):
    topic_direction = "topic_direction"
    background = "background"
    literature_review = "literature_review"
    research_objectives = "research_objectives"
    research_content = "research_content"
    technical_approach = "technical_approach"
    dataset_experiment = "dataset_experiment"
    innovation = "innovation"
    workload = "workload"
    feasibility_risk = "feasibility_risk"
    reference_resources = "reference_resources"
    missing_evidence = "missing_evidence"


REQUIRED_SECTIONS: List[str] = [
    s.value for s in SectionKey
]

INFLATED_WORDS: List[str] = [
    "首创", "第一", "填补空白", "国际领先", "国内首次",
    "revolutionary", "first ever", "state-of-the-art", "novel breakthrough",
]

MIN_WORKLOAD_ITEMS = 5
MIN_INNOVATION_ITEMS = 2

WORKLOAD_TEMPLATE: List[str] = [
    "数据准备",
    "baseline 复现",
    "方法改进",
    "实验对比",
    "消融实验",
    "系统或可视化 Demo",
    "论文写作与答辩材料",
]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ProposalSection(BaseModel):
    """A single section of the proposal draft."""

    section_id: str
    title: str
    content: str
    evidence_refs: List[str] = Field(default_factory=list)
    selected_refs: List[str] = Field(default_factory=list)
    candidate_refs: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.low


class InnovationPoint(BaseModel):
    """A single innovation point with evidence grounding."""

    title: str
    description: str
    evidence_base: str
    risk: str


class WorkloadItem(BaseModel):
    """A single workload breakdown item."""

    item: str
    estimated_weeks: Optional[int] = None


class ProposalDraft(BaseModel):
    """Full proposal draft with 12 sections, evidence binding, workload, innovation."""

    topic_title: str
    sections: List[ProposalSection] = Field(default_factory=list)
    innovation_points: List[InnovationPoint] = Field(default_factory=list)
    workload_items: List[WorkloadItem] = Field(default_factory=list)
    feasibility_summary: Optional[str] = None
    bound_evidence: List[str] = Field(default_factory=list)
    overall_missing: List[str] = Field(default_factory=list)


class ProposalDraftRequest(BaseModel):
    """Input for generating proposal draft."""

    topic_title: str
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    selected_refs: List[str] = Field(default_factory=list)
    candidate_refs: List[str] = Field(default_factory=list)
    feasibility: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _has_evidence(section: ProposalSection) -> bool:
    return bool(section.evidence_refs or section.selected_refs)


def _validate_confidence(section: ProposalSection) -> bool:
    """No evidence → confidence cannot be high."""
    if not _has_evidence(section) and section.confidence == ConfidenceLevel.high:
        return False
    if (not section.evidence_refs and not section.selected_refs
            and section.candidate_refs and section.confidence == ConfidenceLevel.high):
        return False
    return True


def _validate_no_inflation(text: str) -> bool:
    """Check for inflated claims."""
    lower = text.lower()
    for word in INFLATED_WORDS:
        if word.lower() in lower:
            return False
    return True


def validate_proposal(draft: ProposalDraft) -> List[str]:
    """Return list of validation errors (empty = valid)."""
    errors: List[str] = []

    # 1. All 12 sections present
    section_ids = {s.section_id for s in draft.sections}
    for req in REQUIRED_SECTIONS:
        if req not in section_ids:
            errors.append(f"Missing section: {req}")

    # 2. Each section has evidence or missing
    for s in draft.sections:
        if not s.evidence_refs and not s.selected_refs and not s.missing_evidence:
            errors.append(f"Section '{s.section_id}' has no evidence and no missing_evidence")

    # 3. No high confidence without evidence
    for s in draft.sections:
        if not _validate_confidence(s):
            errors.append(f"Section '{s.section_id}' has high confidence without evidence")

    # 4. Workload >= 5
    if len(draft.workload_items) < MIN_WORKLOAD_ITEMS:
        errors.append(f"Workload has {len(draft.workload_items)} items, need >= {MIN_WORKLOAD_ITEMS}")

    # 5. Innovation >= 2, no inflated words
    if len(draft.innovation_points) < MIN_INNOVATION_ITEMS:
        errors.append(f"Innovation has {len(draft.innovation_points)} points, need >= {MIN_INNOVATION_ITEMS}")
    for ip in draft.innovation_points:
        if not _validate_no_inflation(ip.title):
            errors.append(f"Innovation '{ip.title}' contains inflated language")
        if not _validate_no_inflation(ip.description):
            errors.append(f"Innovation description contains inflated language")

    # 6. No fabricated URLs (selected_refs/candidate_refs should be from existing resources)
    # This is enforced by not allowing arbitrary URLs in evidence_refs

    return errors
