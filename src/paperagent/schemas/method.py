from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from paperagent.academic_methodology import MethodPlan
from paperagent.schemas.base import FrozenModel


class BaselineProposal(FrozenModel):
    name: str
    description: str


class MethodModule(FrozenModel):
    module_id: str
    name: str
    purpose: str


class IntegrationContract(FrozenModel):
    from_module: str
    to_module: str
    input: str
    output: str


class ExperimentPlan(FrozenModel):
    name: str
    conditions: list[str]
    metrics: list[str]
    baseline: str
    success_threshold: str


class AblationPlan(FrozenModel):
    name: str
    change: str
    expected_observation: str


class MethodProposal(FrozenModel):
    schema_version: Literal["0.2"] = "0.2"
    status: Literal["proposed"] = "proposed"
    baseline: BaselineProposal
    modules: list[MethodModule]
    integration_contracts: list[IntegrationContract]
    problem_method_insight: str
    falsifiable_hypothesis: str
    minimum_key_experiment: ExperimentPlan
    ablations: list[AblationPlan]
    risks: list[str]
    stop_conditions: list[str]
    evidence_ids: list[str]
    methodology_plan: MethodPlan

    @model_validator(mode="after")
    def validate_canonical_alignment(self) -> MethodProposal:
        legacy_modules = {module.module_id for module in self.modules}
        canonical_modules = {module.name for module in self.methodology_plan.modules}
        if legacy_modules != canonical_modules:
            raise ValueError("legacy method modules must match canonical methodology plan modules")
        legacy_evidence = set(self.evidence_ids)
        canonical_evidence = {item.evidence_id for item in self.methodology_plan.evidence}
        if not canonical_evidence.issubset(legacy_evidence):
            raise ValueError("canonical methodology evidence must be declared in evidence_ids")
        if self.stop_conditions != list(self.methodology_plan.stop_conditions):
            raise ValueError("legacy stop conditions must match canonical methodology plan")
        return self
