"""Re7.5 Full-chain verification — ChangeHypothesis, failure taxonomy, eval harness."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ChangeHypothesis(BaseModel):
    """Record of a single change hypothesis for controlled iteration."""
    change_id: str = Field(default_factory=lambda: _uuid())
    round: int = 0
    failure_signature: str = ""
    hypothesis: str = ""
    change_scope: list[str] = Field(default_factory=list)
    expected_gain: str = ""
    must_not_regress: list[str] = Field(default_factory=list)
    target_tests: list[str] = Field(default_factory=list)
    before_metrics: dict = Field(default_factory=dict)
    after_metrics: dict = Field(default_factory=dict)
    result: Literal["applied", "reverted", "pending"] = "pending"
    created_at: str = Field(default_factory=lambda: _utcnow())


class FailureTaxonomy(BaseModel):
    """Classification of failures by signature."""
    run_id: str = ""
    total_failures: int = 0
    by_signature: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_module: dict[str, int] = Field(default_factory=dict)
    failures: list[dict] = Field(default_factory=list)


class CrossDomainResult(BaseModel):
    """Per-case cross-domain evaluation result."""
    case_id: str = ""
    topic: str = ""
    expected_verdict: str = ""
    actual_verdict: str = ""
    verdict_match: bool = False
    has_evidence: bool = False
    has_fabrication: bool = False
    baseline_count: int = 0
    paper_count: int = 0
    errors: list[str] = Field(default_factory=list)
    fallback_events: int = 0
    duration_s: float = 0.0


class RoundReport(BaseModel):
    """Aggregated round report."""
    round: int = 0
    run_id: str = ""
    test_level: str = "L2"
    started_at: str = ""
    completed_at: str = ""
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    degraded: int = 0
    p0_pass: bool = False
    p1_met: dict[str, bool] = Field(default_factory=dict)
    change_hypotheses: list[ChangeHypothesis] = Field(default_factory=list)
    failure_taxonomy: FailureTaxonomy | None = None
    cross_domain_results: list[CrossDomainResult] = Field(default_factory=list)
    decision: Literal["PASS", "HOLD", "NO_GO"] = "HOLD"
    notes: str = ""


# Failure signature taxonomy
FAILURE_SIGNATURES = {
    "json_field_drift": "JSON parse or schema validation failure — field missing or wrong type",
    "empty_repair": "targeted_repair generates no queries — search stalls",
    "empty_expansion": "citation_expander returns no new papers — verify skipped incorrectly",
    "cross_domain_misjudge": "verdict disagrees with human rubric for cross-domain case",
    "novelty_pseudo_innovation": "novelty claim is engineering stack or performance-only",
    "rag_no_citation": "RAG answer lacks required chunk citation",
    "rag_fabrication": "RAG answer cites non-existent chunk or document",
    "rag_abstain_fail": "RAG fails to abstain when no relevant chunks exist",
    "job_stuck": "job remains pending/running beyond timeout",
    "job_cancel_fail": "cancelled job continues making LLM calls",
    "budget_exceed_no_partial": "budget exceeded but no partial results saved",
    "feedback_leak": "user feedback enters LLM context or prompt",
    "provider_drift": "provider returns different shape/format across runs",
    "fallback_hidden": "fallback occurs but not reported in trace",
}


def _uuid() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
