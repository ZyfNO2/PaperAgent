"""Re6.4.1 Method Tailoring Gate — engineering contracts for method landing.

BaselineCard, ModuleCard, CompatibilityMatrix, MethodHypothesis,
ExperimentMatrix, MethodDecision.

Gate chain: G0 scope → G1 evidence → G2 baseline → G3 hypothesis →
            G4 integration → G5 experiment → GO/REVISE/NO_GO
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BaselineCard(BaseModel):
    """Reproducible baseline contract."""
    paper_id: str = ""
    doi: str = ""
    repo_url: str = ""
    commit_hash: str = ""
    license_type: str = "unknown"
    dataset: str = ""
    data_split: str = ""
    environment: str = ""
    reported_metric: str = ""
    reported_value: float | str = ""
    reproduced_metric: str | None = None
    reproduced_value: float | None = None
    status: Literal["reproduced", "repro_failed", "not_attempted", "blocked"] = "not_attempted"
    provenance: Literal["verified", "inferred", "proposed", "unknown"] = "unknown"

    @model_validator(mode="after")
    def _validate_baseline(self) -> "BaselineCard":
        if self.status == "reproduced" and not self.reproduced_value:
            raise ValueError("reproduced baseline must have reproduced_value")
        return self


class ModuleCard(BaseModel):
    """A borrowed module with semantic contracts."""
    module_id: str = Field(default_factory=lambda: _uuid())
    source: str = ""           # paper/DOI/repo
    license_type: str = "unknown"
    original_role: str = ""
    new_role: str = ""
    input_spec: str = ""       # dtype, shape, range, semantics
    output_spec: str = ""      # dtype, shape, range, semantics
    dtype: str = "float32"
    scale_normalization: str = "none"
    spatial_order: str = "C-order (default)"
    mask_handling: str = "none"
    gradient_flow: str = "native"
    loss_dependency: str = "none"
    compute_budget: str = ""
    failure_mode: str = ""
    status: Literal["verified", "inferred", "proposed", "unknown"] = "proposed"


class CompatibilityMatrix(BaseModel):
    """Edge-wise semantic compatibility between producer→consumer modules."""
    producer_id: str = ""
    consumer_id: str = ""
    semantic_unit: str = ""
    shape_compat: str = ""
    normalization_compat: str = ""
    spatial_order_compat: str = ""
    mask_compat: str = ""
    gradient_compat: str = ""
    test_exists: bool = False
    test_description: str = ""
    status: Literal["validated", "shape_only", "untested", "incompatible"] = "untested"

    def is_semantically_safe(self) -> bool:
        return self.status == "validated"


class MethodHypothesis(BaseModel):
    """Falsifiable method hypothesis with guardrails."""
    hypothesis_id: str = Field(default_factory=lambda: _uuid())
    condition_c: str = ""      # When does this apply?
    limitation_l: str = ""     # When does it break?
    mechanism_m: str = ""      # Causal mechanism
    intervention_b: str = ""   # Module change
    observable_y: str = ""     # Measurable outcome
    guardrail_g: str = ""      # Safety check / bound
    falsifier: str = ""        # What would disprove this?
    status: Literal["verified", "inferred", "proposed", "unknown"] = "proposed"

    @model_validator(mode="after")
    def _validate_gate3(self) -> "MethodHypothesis":
        missing = []
        if not self.guardrail_g:
            missing.append("guardrail_g")
        if not self.falsifier:
            missing.append("falsifier")
        if missing:
            raise ValueError(
                f"G3 gate failed: hypothesis must have guardrail and falsifier. "
                f"Missing: {missing}"
            )
        return self


class ExperimentMatrix(BaseModel):
    """Fair experiment plan with pre-declared conditions."""
    experiment_id: str = Field(default_factory=lambda: _uuid())
    frozen_baseline: str = ""        # baseline commit/config hash
    single_module: list[str] = Field(default_factory=list)
    leave_one_out: list[str] = Field(default_factory=list)
    full_method: str = ""
    compute_matched_control: str = ""
    fixed_split: str = ""
    fixed_seeds: list[int] = Field(default_factory=list)
    compute_budget: str = ""
    stop_condition: str = ""
    ablation_matrix: list[dict] = Field(default_factory=list)
    status: Literal["verified", "inferred", "proposed", "unknown"] = "proposed"


class MethodDecision(BaseModel):
    """Go/Revise/No-go decision with evidence trace."""
    decision_id: str = Field(default_factory=lambda: _uuid())
    verdict: Literal["GO", "REVISE", "NO_GO"] = "REVISE"
    confidence: float = 0.5
    gates_passed: list[str] = Field(default_factory=list)
    gates_failed: list[str] = Field(default_factory=list)
    evidence_missing: list[str] = Field(default_factory=list)
    stop_condition: str = ""
    rationale: str = ""

    @model_validator(mode="after")
    def _validate_decision(self) -> "MethodDecision":
        if self.verdict == "GO" and self.evidence_missing:
            raise ValueError(
                "cannot GO with missing evidence: " + ", ".join(self.evidence_missing)
            )
        if self.verdict == "NO_GO" and not self.stop_condition:
            raise ValueError("NO_GO requires a stop_condition")
        return self


def _uuid() -> str:
    import uuid
    return uuid.uuid4().hex[:12]
