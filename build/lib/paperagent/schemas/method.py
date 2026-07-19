from __future__ import annotations

from typing import Literal

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
    schema_version: Literal["0.1"] = "0.1"
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
