from __future__ import annotations

from typing import Literal

from pydantic import Field

from paperagent.schemas.base import FrozenModel


class Claim(FrozenModel):
    claim_id: str
    text: str
    evidence_ids: list[str]


class GapAssessment(FrozenModel):
    gap_id: str
    status: Literal["supported", "partial", "unsupported", "conflicted"]
    evidence_ids: list[str]
    summary: str
    limitations: list[str] = Field(default_factory=list)


class ConflictAssessment(FrozenModel):
    conflict_id: str
    evidence_ids: list[str]
    summary: str


class EvidenceSynthesis(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    gap_assessments: list[GapAssessment]
    verified_findings: list[Claim]
    conflicts: list[ConflictAssessment]
    feasibility: Literal["feasible", "partially_feasible", "not_feasible", "unknown"]
    limitations: list[str]

    def referenced_evidence_ids(self) -> set[str]:
        ids: set[str] = set()
        for assessment in self.gap_assessments:
            ids.update(assessment.evidence_ids)
        for claim in self.verified_findings:
            ids.update(claim.evidence_ids)
        for conflict in self.conflicts:
            ids.update(conflict.evidence_ids)
        return ids
