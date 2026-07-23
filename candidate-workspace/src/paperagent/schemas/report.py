from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel


class ReportClaim(FrozenModel):
    text: str
    evidence_ids: list[str]


class FinalReport(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    status: Literal["completed", "blocked", "partial"]
    executive_summary: str
    verified_findings: list[ReportClaim]
    inferred_findings: list[ReportClaim]
    proposed_method: str | None = None
    experiment_plan: str | None = None
    limitations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report(self) -> FinalReport:
        if self.status in {"completed", "blocked"} and not self.limitations:
            raise ValueError(f"{self.status} report requires limitations")
        return self
