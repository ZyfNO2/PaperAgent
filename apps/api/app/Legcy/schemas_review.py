"""Session 30: 委员会复核 schema — ReviewRound + Issue + RevisionAction."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReviewVerdict(str, Enum):
    pass_ = "pass"
    conditional_pass = "conditional_pass"
    revise = "revise"
    reject = "reject"


class Severity(str, Enum):
    fatal = "fatal"
    high = "high"
    medium = "medium"
    low = "low"


class RevisionActionType(str, Enum):
    accept_fix = "accept_fix"
    ignore_issue = "ignore_issue"
    add_evidence = "add_evidence"
    revise_keywords = "revise_keywords"
    revise_topic = "revise_topic"
    regenerate_section = "regenerate_section"
    rerun_review = "rerun_review"


class ReviewPerspective(str, Enum):
    advisor = "advisor"       # 导师视角：题目是否可控
    method = "method"         # 方法视角：技术路线是否说得通
    experiment = "experiment" # 实验视角：数据、baseline、指标
    writing = "writing"       # 写作视角：报告结构
    risk = "risk"             # 风险视角：毕业风险


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ReviewIssue(BaseModel):
    """A single issue found during review."""

    issue_id: str
    perspective: ReviewPerspective
    severity: Severity
    section_id: str
    message: str
    suggested_fix: str
    evidence_refs: List[str] = Field(default_factory=list)
    resolved: bool = False


class RevisionAction(BaseModel):
    """An action the user can take on an issue."""

    action_id: str
    action_type: RevisionActionType
    target_issue_id: str
    description: str
    section_id: Optional[str] = None


class ReviewRound(BaseModel):
    """A single review round with issues and actions."""

    round_id: int
    verdict: ReviewVerdict
    issues: List[ReviewIssue] = Field(default_factory=list)
    required_actions: List[RevisionAction] = Field(default_factory=list)
    optional_actions: List[RevisionAction] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    next_revision_prompt: str = ""


class ReviewHistory(BaseModel):
    """History of all review rounds."""

    topic_title: str
    rounds: List[ReviewRound] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    """Request to run a review on a proposal draft."""

    topic_title: str
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    feasibility: Optional[Dict[str, Any]] = None
    revision_actions: List[Dict[str, Any]] = Field(default_factory=list)


class RevisionActionRequest(BaseModel):
    """Request to execute a revision action."""

    action_type: RevisionActionType
    issue_id: str
    section_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def can_verdict_pass(round_data: ReviewRound) -> bool:
    """Fatal issues must be resolved before pass."""
    unresolved_fatal = [
        i for i in round_data.issues
        if i.severity == Severity.fatal and not i.resolved
    ]
    return len(unresolved_fatal) == 0
