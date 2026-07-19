from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel


class FinalOutcome(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    execution_status: Literal["running", "succeeded", "blocked", "failed", "cancelled"]
    scientific_verdict: Literal["GO", "REVISE", "NO_GO", "NOT_EVALUATED"]
    quality_route: Literal[
        "pass",
        "repair_retrieval",
        "repair_method",
        "human_review",
        "blocked",
    ]
    report_status: Literal["completed", "partial", "blocked"]
    reason_codes: list[str] = Field(default_factory=list)
    blocker_code: str | None = None
    missing_gap_ids: list[str] = Field(default_factory=list)
    invalid_evidence_ids: list[str] = Field(default_factory=list)
    methodology_audit_fingerprint: str | None = None
    evidence_ledger_fingerprint: str | None = None
    recommended_next_actions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_outcome(self) -> FinalOutcome:
        if (
            self.scientific_verdict in {"GO", "REVISE", "NO_GO"}
            and self.report_status != "completed"
        ):
            raise ValueError("scientific verdicts require a completed report")
        if self.scientific_verdict == "NOT_EVALUATED" and self.execution_status == "succeeded":
            raise ValueError("NOT_EVALUATED cannot use succeeded execution status")
        if self.scientific_verdict == "GO" and self.quality_route != "pass":
            raise ValueError("GO requires quality_route=pass")
        if self.scientific_verdict == "REVISE" and not self.recommended_next_actions:
            raise ValueError("REVISE requires recommended_next_actions")
        if self.execution_status == "failed" and self.scientific_verdict != "NOT_EVALUATED":
            raise ValueError("failed execution cannot produce a scientific verdict")
        return self


class TraceInvariantResult(FrozenModel):
    invariant_id: str
    passed: bool
    details: str | None = None


class TraceAuditResult(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    passed: bool
    results: list[TraceInvariantResult]
    error_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_audit(self) -> TraceAuditResult:
        derived_passed = all(result.passed for result in self.results)
        if self.passed != derived_passed:
            raise ValueError("trace audit passed flag must be derived from invariant results")
        if self.passed and self.error_codes:
            raise ValueError("passing trace audit cannot contain error codes")
        if not self.passed and not self.error_codes:
            raise ValueError("failed trace audit requires error codes")
        return self
