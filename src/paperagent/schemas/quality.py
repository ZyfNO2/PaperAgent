from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel


class QualityDecision(FrozenModel):
    verdict: Literal["pass", "repair_retrieval", "repair_method", "human_review", "blocked"]
    reason_codes: list[str]
    repair_target: Literal["retrieval", "method"] | None = None
    missing_gap_ids: list[str] = Field(default_factory=list)
    invalid_evidence_ids: list[str] = Field(default_factory=list)
    human_question: str | None = None

    @model_validator(mode="after")
    def validate_repair_contract(self) -> QualityDecision:
        expected = {
            "repair_retrieval": "retrieval",
            "repair_method": "method",
        }.get(self.verdict)
        if expected is not None and self.repair_target != expected:
            raise ValueError(f"{self.verdict} requires repair_target={expected}")
        if expected is None and self.repair_target is not None:
            raise ValueError("non-repair verdict cannot set repair_target")
        if self.verdict == "human_review" and not self.human_question:
            raise ValueError("human_review requires human_question")
        return self
