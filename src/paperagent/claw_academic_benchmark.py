from __future__ import annotations

import hashlib
import hmac
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel

SOURCE_REPOSITORY = "ZyfNO2/PaperClaw"
SOURCE_BRANCH = "main"
SOURCE_COMMIT = "60a577a3d8d6701a8d212604572e846cc8a41e2f"
SOURCE_DATASET_PATH = "evals/academic_tailoring_v1"
CASE_SCHEMA = "paperclaw.academic-tailoring.case.v1"
PROFILE_SCHEMA = "paperclaw.academic-tailoring.trace-profile.v1"
PROFILE_ID = "academic-tailoring-gold-trace-v1"
RUN_TRACE_SCHEMA = "paperagent.claw-academic-run.v1"
REPORT_SCHEMA = "paperagent.claw-academic-report.v1"

StageName = Literal[
    "parse_user_input",
    "exploratory_retrieval",
    "relevance_review",
    "clarification_gate",
    "freeze_baseline",
    "gap_hypothesis",
    "module_compatibility",
    "minimal_stitch",
    "experiment_matrix",
    "decision",
]
Decision = Literal["GO", "REVISE", "REVISE_TO_PILOT", "NO_GO"]
ObservedDecision = Literal["GO", "REVISE", "NO_GO"]
EvidenceRole = Literal[
    "baseline",
    "gap",
    "parallel_method",
    "strong_comparison",
    "risk",
    "other",
]
ExperimentArm = Literal[
    "baseline",
    "single_module",
    "full",
    "strong_comparison",
    "interaction",
    "efficiency",
    "negative_control",
    "feasibility",
]
HardFailureCode = Literal[
    "FABRICATED_ITEM",
    "IDENTITY_ONLY_ACCEPTANCE",
    "FORCED_INCOMPATIBLE_SUPPLIED_MATERIAL",
    "COMPOSITION_ONLY_NOVELTY",
    "FUTURE_OR_TEST_LEAKAGE",
    "HIDDEN_STRONGER_BASELINE_OR_NEGATIVE_RESULT",
    "SUCCESS_WITHOUT_REPRODUCIBLE_BASELINE_OR_HYPOTHESIS",
    "TRACE_CONTRACT_FAILURE",
]

STAGE_ORDER: tuple[StageName, ...] = (
    "parse_user_input",
    "exploratory_retrieval",
    "relevance_review",
    "clarification_gate",
    "freeze_baseline",
    "gap_hypothesis",
    "module_compatibility",
    "minimal_stitch",
    "experiment_matrix",
    "decision",
)
STAGE_WEIGHTS: dict[StageName, int] = {
    "parse_user_input": 10,
    "exploratory_retrieval": 8,
    "relevance_review": 7,
    "clarification_gate": 10,
    "freeze_baseline": 15,
    "gap_hypothesis": 15,
    "module_compatibility": 15,
    "minimal_stitch": 10,
    "experiment_matrix": 5,
    "decision": 5,
}
EXPECTED_SNAPSHOT_FILES = {
    "cases-01.jsonl",
    "cases-02.jsonl",
    "cases-03.jsonl",
    "cases-04.jsonl",
    "trace-profile.json",
}
EXPECTED_RETRIEVAL_ROLES: set[EvidenceRole] = {
    "baseline",
    "gap",
    "parallel_method",
    "strong_comparison",
    "risk",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _git_blob_sha(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324


def _present(value: str | None) -> bool:
    return value is not None and bool(value.strip())


class DatasetSource(FrozenModel):
    schema: Literal["paperagent.external-dataset-source.v1"]
    dataset_id: Literal["claw-academic-tailoring-v1"]
    source_repository: Literal["ZyfNO2/PaperClaw"]
    source_branch: Literal["main"]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_path: Literal["evals/academic_tailoring_v1"]
    mode: Literal["read_only_snapshot"]
    files: dict[str, str]
    notes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_source(self) -> DatasetSource:
        if self.source_commit != SOURCE_COMMIT:
            raise ValueError("unexpected PaperClaw source commit")
        if set(self.files) != EXPECTED_SNAPSHOT_FILES:
            raise ValueError("snapshot source file set is incomplete or unknown")
        if any(len(value) != 40 for value in self.files.values()):
            raise ValueError("source blob SHAs must be full Git SHA-1 values")
        return self


class TraceStage(FrozenModel):
    stage: StageName
    expected: str = Field(min_length=1)


class TraceProfile(FrozenModel):
    schema: Literal["paperclaw.academic-tailoring.trace-profile.v1"]
    profile_id: Literal["academic-tailoring-gold-trace-v1"]
    stages: tuple[TraceStage, ...]
    global_hard_failures: tuple[str, ...]

    @model_validator(mode="after")
    def validate_profile(self) -> TraceProfile:
        if tuple(item.stage for item in self.stages) != STAGE_ORDER:
            raise ValueError("trace profile stages must match the canonical ten-stage order")
        if len(self.global_hard_failures) != 7:
            raise ValueError("trace profile must declare all seven global hard failures")
        return self


class SuppliedMaterial(FrozenModel):
    count: Literal[1]
    declared_role: str = Field(min_length=1)
    title: str = Field(min_length=1)


class SpecialAssertions(FrozenModel):
    required: tuple[str, ...]
    forbidden: tuple[str, ...]

    @model_validator(mode="after")
    def validate_assertions(self) -> SpecialAssertions:
        if not self.required or not self.forbidden:
            raise ValueError("required and forbidden assertions must both be non-empty")
        return self


class GoldCase(FrozenModel):
    schema: Literal["paperclaw.academic-tailoring.case.v1"]
    case_id: str = Field(pattern=r"^at-[0-9]{3}-[a-z0-9-]+$")
    user_input: str = Field(min_length=1)
    supplied_materials: tuple[SuppliedMaterial, ...]
    intent: dict[str, Any]
    unknowns: tuple[str, ...]
    clarification_questions: tuple[str, ...]
    baseline_expectation: dict[str, Any]
    parallel_expectations: tuple[dict[str, Any], ...]
    hypothesis: str = Field(min_length=1)
    tailoring_advice: dict[str, Any]
    experiment_plan: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    decision: Decision
    special_assertions: SpecialAssertions
    tags: tuple[str, ...]
    trace_profile: Literal["academic-tailoring-gold-trace-v1"]

    @model_validator(mode="after")
    def validate_case(self) -> GoldCase:
        if len(self.supplied_materials) > 2:
            raise ValueError("a gold case may contain at most two supplied papers")
        if not 1 <= len(self.clarification_questions) <= 2:
            raise ValueError("a gold case requires one or two clarification questions")
        if not self.unknowns:
            raise ValueError("gold case unknowns must be explicit")
        if not self.parallel_expectations:
            raise ValueError("gold case parallel expectations must be non-empty")
        if not self.experiment_plan or not self.stop_conditions or not self.tags:
            raise ValueError("gold case experiment, stop, and tag fields must be non-empty")
        return self


class GoldDataset(FrozenModel):
    source: DatasetSource
    profile: TraceProfile
    cases: tuple[GoldCase, ...]
    dataset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_dataset(self) -> GoldDataset:
        if len(self.cases) != 20:
            raise ValueError("PaperClaw academic-tailoring snapshot must contain 20 cases")
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("PaperClaw academic-tailoring case IDs must be unique")
        supplied_counts = Counter(len(item.supplied_materials) for item in self.cases)
        if supplied_counts != Counter({0: 15, 1: 3, 2: 2}):
            raise ValueError("supplied-paper distribution must remain 15/3/2")
        expected_digest = _sha256(
            {
                "source": self.source.model_dump(mode="json"),
                "profile": self.profile.model_dump(mode="json"),
                "cases": [item.model_dump(mode="json") for item in self.cases],
            }
        )
        if not hmac.compare_digest(self.dataset_digest, expected_digest):
            raise ValueError("dataset digest does not match the imported snapshot")
        return self


class FactPartitions(FrozenModel):
    verified: tuple[str, ...] = ()
    inferred: tuple[str, ...] = ()
    proposed: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()


class EvidenceReview(FrozenModel):
    evidence_id: str = Field(min_length=1)
    source_type: Literal["paper", "dataset", "repository", "web", "user_material"]
    identity_verified: bool
    relevance_reviewed: bool
    relevance_passed: bool
    accepted: bool
    role: EvidenceRole | None = None
    gap_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    core_evidence: bool = False
    full_text_checked: bool = False
    source_is_supplied_material: bool = False
    role_compatible: bool | None = None


class BaselineTrace(FrozenModel):
    name: str = Field(min_length=1)
    source_evidence_id: str | None = None
    version_or_commit: str | None = None
    dataset: str | None = None
    split: str | None = None
    metrics: tuple[str, ...] = ()
    environment: str | None = None
    seed_policy: str | None = None
    compute_assumptions: str | None = None
    disabled_module_parity_path: str | None = None
    baseline_parity_verified: bool | None = None
    reproduced: bool = False
    reproduced_metric: str | None = None
    strong_comparisons: tuple[str, ...] = ()


class HypothesisTrace(FrozenModel):
    condition: str | None = None
    limitation: str | None = None
    mechanism: str | None = None
    intervention: str | None = None
    target_metric: str | None = None
    guardrail: str | None = None


class ModuleTrace(FrozenModel):
    module_id: str = Field(min_length=1)
    evidence_id: str | None = None
    original_role: str | None = None
    proposed_role: str | None = None
    input_semantics: str | None = None
    output_semantics: str | None = None
    input_shape: str | None = None
    output_shape: str | None = None
    optimization_interaction: str | None = None
    compute_cost: str | None = None
    failure_mode: str | None = None
    implementation_switch: str | None = None
    role_compatible: bool | None = None


class ExperimentTrace(FrozenModel):
    experiment_id: str = Field(min_length=1)
    arm_type: ExperimentArm
    included_modules: tuple[str, ...] = ()
    dataset: str | None = None
    split: str | None = None
    preprocessing: str | None = None
    tuning_budget: str | None = None
    metrics: tuple[str, ...] = ()
    seeds: tuple[int, ...] = ()
    uncertainty_reporting: str | None = None
    resource_measures: tuple[str, ...] = ()
    stopping_criteria: str | None = None


class AcademicTailoringRunTrace(FrozenModel):
    schema: Literal["paperagent.claw-academic-run.v1"] = RUN_TRACE_SCHEMA
    case_id: str = Field(min_length=1)
    fact_partitions: FactPartitions
    retrieval_roles: tuple[EvidenceRole, ...]
    evidence_reviews: tuple[EvidenceReview, ...]
    clarification_questions: tuple[str, ...]
    resolved_unknowns: tuple[str, ...]
    asked_user_to_design_method: bool = False
    baseline: BaselineTrace | None = None
    hypothesis: HypothesisTrace | None = None
    modules: tuple[ModuleTrace, ...] = ()
    module_design_deferred: bool = False
    module_defer_reason: str | None = None
    stitch_order: tuple[str, ...] = ()
    experiments: tuple[ExperimentTrace, ...] = ()
    decision: ObservedDecision
    pilot_recommended: bool = False
    next_actions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    stronger_baselines_considered: bool
    negative_results_visible: bool
    fabricated_items: tuple[str, ...] = ()
    novelty_claimed_from_composition_only: bool = False
    future_or_test_leakage: bool = False
    trace_audit_passed: bool | None = None
    trace_error_codes: tuple[str, ...] = ()


class StageScore(FrozenModel):
    stage: StageName
    earned: int = Field(ge=0)
    available: int = Field(ge=1)
    passed: bool
    findings: tuple[str, ...]

    @model_validator(mode="after")
    def validate_score(self) -> StageScore:
        if self.earned > self.available:
            raise ValueError("stage earned score cannot exceed available score")
        if self.passed != (self.earned == self.available):
            raise ValueError("stage pass flag must be derived from earned score")
        return self


class HardFailure(FrozenModel):
    code: HardFailureCode
    details: str = Field(min_length=1)


class CaseEvaluation(FrozenModel):
    case_id: str
    status: Literal["passed", "failed"]
    score: int = Field(ge=0, le=100)
    minimum_score: int = Field(ge=0, le=100)
    expected_decision: Decision
    observed_decision: Decision
    decision_matches: bool
    hard_failures: tuple[HardFailure, ...]
    stages: tuple[StageScore, ...]
    tags: tuple[str, ...]

    @model_validator(mode="after")
    def validate_case_result(self) -> CaseEvaluation:
        if tuple(item.stage for item in self.stages) != STAGE_ORDER:
            raise ValueError("case stage results must preserve canonical order")
        if self.score != sum(item.earned for item in self.stages):
            raise ValueError("case score must be derived from stage scores")
        expected_status = (
            "passed"
            if self.score >= self.minimum_score
            and self.decision_matches
            and not self.hard_failures
            else "failed"
        )
        if self.status != expected_status:
            raise ValueError("case status must be derived from score, decision, and blockers")
        return self


class AggregateEvaluation(FrozenModel):
    schema: Literal["paperagent.claw-academic-report.v1"] = REPORT_SCHEMA
    source_repository: Literal["ZyfNO2/PaperClaw"] = SOURCE_REPOSITORY
    source_commit: Literal[
        "60a577a3d8d6701a8d212604572e846cc8a41e2f"
    ] = SOURCE_COMMIT
    dataset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    total: int = Field(ge=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    average_score: float = Field(ge=0.0, le=100.0)
    decision_accuracy: float = Field(ge=0.0, le=1.0)
    hard_failure_count: int = Field(ge=0)
    by_tag: dict[str, dict[str, int]]
    cases: tuple[CaseEvaluation, ...]
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_aggregate(self) -> AggregateEvaluation:
        if self.total != len(self.cases):
            raise ValueError("aggregate total must equal case result count")
        if self.passed != sum(item.status == "passed" for item in self.cases):
            raise ValueError("aggregate passed count must be derived from case results")
        if self.failed != self.total - self.passed:
            raise ValueError("aggregate failed count must be derived from total and passed")
        expected_hard_failures = sum(len(item.hard_failures) for item in self.cases)
        if self.hard_failure_count != expected_hard_failures:
            raise ValueError("aggregate hard failure count must be derived from case results")
        payload = self.model_dump(mode="json", exclude={"report_digest"})
        expected_digest = _sha256(payload)
        if not hmac.compare_digest(self.report_digest, expected_digest):
            raise ValueError("aggregate report digest mismatch")
        return self


def load_gold_dataset(root: Path) -> GoldDataset:
    source = DatasetSource.model_validate_json((root / "source.json").read_text(encoding="utf-8"))
    for filename, expected_blob in source.files.items():
        payload = (root / filename).read_bytes()
        actual_blob = _git_blob_sha(payload)
        if actual_blob != expected_blob:
            raise ValueError(
                f"snapshot file {filename} diverges from PaperClaw blob {expected_blob}"
            )
    profile = TraceProfile.model_validate_json(
        (root / "trace-profile.json").read_text(encoding="utf-8")
    )
    shards = sorted(root.glob("cases-*.jsonl"))
    if len(shards) != 4:
        raise ValueError(f"expected four case shards, found {len(shards)}")
    cases: list[GoldCase] = []
    for shard in shards:
        for line_number, line in enumerate(
            shard.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                cases.append(GoldCase.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"{shard.name}:{line_number}: {exc}") from exc
    payload = {
        "source": source.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "cases": [item.model_dump(mode="json") for item in cases],
    }
    return GoldDataset(
        source=source,
        profile=profile,
        cases=tuple(cases),
        dataset_digest=_sha256(payload),
    )


def _partition_sets(partitions: FactPartitions) -> tuple[set[str], ...]:
    return (
        set(partitions.verified),
        set(partitions.inferred),
        set(partitions.proposed),
        set(partitions.unknown),
    )


def _partitions_are_disjoint(partitions: FactPartitions) -> bool:
    values = _partition_sets(partitions)
    return all(not left & right for index, left in enumerate(values) for right in values[index + 1 :])


def _hypothesis_complete(hypothesis: HypothesisTrace | None) -> bool:
    if hypothesis is None:
        return False
    return all(
        _present(value)
        for value in (
            hypothesis.condition,
            hypothesis.limitation,
            hypothesis.mechanism,
            hypothesis.intervention,
            hypothesis.target_metric,
            hypothesis.guardrail,
        )
    )


def _module_complete(module: ModuleTrace) -> bool:
    return all(
        _present(value)
        for value in (
            module.evidence_id,
            module.original_role,
            module.proposed_role,
            module.input_semantics,
            module.output_semantics,
            module.input_shape,
            module.output_shape,
            module.optimization_interaction,
            module.compute_cost,
            module.failure_mode,
            module.implementation_switch,
        )
    ) and module.role_compatible is True


def _experiment_complete(experiment: ExperimentTrace) -> bool:
    return (
        _present(experiment.dataset)
        and _present(experiment.split)
        and _present(experiment.preprocessing)
        and _present(experiment.tuning_budget)
        and bool(experiment.metrics)
        and bool(experiment.seeds)
        and _present(experiment.uncertainty_reporting)
        and bool(experiment.resource_measures)
        and _present(experiment.stopping_criteria)
    )


def _observed_decision(trace: AcademicTailoringRunTrace) -> Decision:
    if trace.decision == "REVISE" and trace.pilot_recommended:
        return "REVISE_TO_PILOT"
    return trace.decision


def _score_stage(
    stage: StageName,
    checks: tuple[tuple[bool, str], ...],
) -> StageScore:
    available = STAGE_WEIGHTS[stage]
    passed_count = sum(passed for passed, _ in checks)
    earned = round(available * passed_count / len(checks)) if checks else 0
    findings = tuple(message for passed, message in checks if not passed)
    return StageScore(
        stage=stage,
        earned=earned,
        available=available,
        passed=earned == available,
        findings=findings,
    )


def _hard_failures(trace: AcademicTailoringRunTrace) -> tuple[HardFailure, ...]:
    failures: list[HardFailure] = []
    if trace.fabricated_items:
        failures.append(
            HardFailure(
                code="FABRICATED_ITEM",
                details="fabricated artifacts: " + ", ".join(trace.fabricated_items),
            )
        )
    invalid_acceptance = [
        item.evidence_id
        for item in trace.evidence_reviews
        if item.accepted
        and (
            not item.identity_verified
            or not item.relevance_reviewed
            or not item.relevance_passed
            or item.role is None
            or not (item.gap_ids or item.claim_ids)
        )
    ]
    if invalid_acceptance:
        failures.append(
            HardFailure(
                code="IDENTITY_ONLY_ACCEPTANCE",
                details="accepted without identity, relevance, and role binding: "
                + ", ".join(invalid_acceptance),
            )
        )
    incompatible_supplied = [
        item.evidence_id
        for item in trace.evidence_reviews
        if item.source_is_supplied_material
        and item.accepted
        and item.role_compatible is False
    ]
    if incompatible_supplied:
        failures.append(
            HardFailure(
                code="FORCED_INCOMPATIBLE_SUPPLIED_MATERIAL",
                details="incompatible supplied material forced into plan: "
                + ", ".join(incompatible_supplied),
            )
        )
    if trace.novelty_claimed_from_composition_only:
        failures.append(
            HardFailure(
                code="COMPOSITION_ONLY_NOVELTY",
                details="novelty was claimed from module composition alone",
            )
        )
    if trace.future_or_test_leakage:
        failures.append(
            HardFailure(
                code="FUTURE_OR_TEST_LEAKAGE",
                details="future/test information or unfair comparison was detected",
            )
        )
    if not trace.stronger_baselines_considered or not trace.negative_results_visible:
        failures.append(
            HardFailure(
                code="HIDDEN_STRONGER_BASELINE_OR_NEGATIVE_RESULT",
                details="stronger baselines or negative results were not preserved",
            )
        )
    baseline = trace.baseline
    if trace.decision == "GO" and (
        baseline is None
        or not baseline.reproduced
        or not baseline.baseline_parity_verified
        or not _hypothesis_complete(trace.hypothesis)
    ):
        failures.append(
            HardFailure(
                code="SUCCESS_WITHOUT_REPRODUCIBLE_BASELINE_OR_HYPOTHESIS",
                details="GO requires reproduced baseline, parity, and falsifiable hypothesis",
            )
        )
    if trace.trace_audit_passed is False:
        failures.append(
            HardFailure(
                code="TRACE_CONTRACT_FAILURE",
                details="trace audit failed: " + ", ".join(trace.trace_error_codes),
            )
        )
    return tuple(failures)


def evaluate_case(
    case: GoldCase,
    trace: AcademicTailoringRunTrace,
    *,
    minimum_score: int = 80,
) -> CaseEvaluation:
    if trace.case_id != case.case_id:
        raise ValueError("candidate trace case ID does not match gold case")
    review_by_id = {item.evidence_id: item for item in trace.evidence_reviews}
    accepted_reviews = tuple(item for item in trace.evidence_reviews if item.accepted)
    accepted_core_reviews = tuple(item for item in accepted_reviews if item.core_evidence)
    supplied_reviews = tuple(
        item for item in trace.evidence_reviews if item.source_is_supplied_material
    )
    expected_unknowns = set(case.unknowns)
    resolved_unknowns = set(trace.resolved_unknowns)
    observed_decision = _observed_decision(trace)
    baseline = trace.baseline
    baseline_source_accepted = (
        baseline is not None
        and baseline.source_evidence_id is not None
        and baseline.source_evidence_id in review_by_id
        and review_by_id[baseline.source_evidence_id].accepted
    )
    baseline_complete = baseline is not None and all(
        (
            _present(baseline.version_or_commit),
            _present(baseline.dataset),
            _present(baseline.split),
            bool(baseline.metrics),
            _present(baseline.environment),
            _present(baseline.seed_policy),
            _present(baseline.compute_assumptions),
            _present(baseline.disabled_module_parity_path),
            bool(baseline.strong_comparisons),
        )
    )
    module_defer_valid = (
        trace.module_design_deferred
        and trace.decision in {"REVISE", "NO_GO"}
        and _present(trace.module_defer_reason)
    )
    modules_complete = bool(trace.modules) and all(
        _module_complete(item) for item in trace.modules
    )
    module_ids = tuple(item.module_id for item in trace.modules)
    experiments_complete = bool(trace.experiments) and all(
        _experiment_complete(item) for item in trace.experiments
    )
    experiment_arms = {item.arm_type for item in trace.experiments}
    stages = (
        _score_stage(
            "parse_user_input",
            (
                (
                    bool(
                        trace.fact_partitions.verified
                        or trace.fact_partitions.inferred
                        or trace.fact_partitions.proposed
                    ),
                    "explicit facts, inferences, or proposals were not recorded",
                ),
                (bool(trace.fact_partitions.unknown), "unknown facts were not recorded"),
                (
                    _partitions_are_disjoint(trace.fact_partitions),
                    "verified, inferred, proposed, and unknown partitions overlap",
                ),
                (
                    len(supplied_reviews) == len(case.supplied_materials),
                    "supplied-paper roles were not tracked exactly",
                ),
            ),
        ),
        _score_stage(
            "exploratory_retrieval",
            tuple(
                (
                    role in set(trace.retrieval_roles),
                    f"retrieval role {role} is missing",
                )
                for role in sorted(EXPECTED_RETRIEVAL_ROLES)
            ),
        ),
        _score_stage(
            "relevance_review",
            (
                (bool(trace.evidence_reviews), "no evidence reviews were recorded"),
                (
                    all(item.relevance_reviewed for item in trace.evidence_reviews),
                    "one or more candidates skipped relevance review",
                ),
                (
                    all(
                        item.identity_verified
                        and item.relevance_passed
                        and item.role is not None
                        and bool(item.gap_ids or item.claim_ids)
                        for item in accepted_reviews
                    ),
                    "accepted evidence lacks identity, relevance, or role binding",
                ),
                (
                    all(item.full_text_checked for item in accepted_core_reviews),
                    "core accepted evidence lacks full-text review",
                ),
            ),
        ),
        _score_stage(
            "clarification_gate",
            (
                (
                    1 <= len(trace.clarification_questions) <= 2,
                    "clarification count must remain between one and two",
                ),
                (
                    bool(expected_unknowns & resolved_unknowns),
                    "clarification did not target a declared high-impact unknown",
                ),
                (
                    not trace.asked_user_to_design_method,
                    "the user was asked to design the method",
                ),
            ),
        ),
        _score_stage(
            "freeze_baseline",
            (
                (baseline is not None, "baseline card is missing"),
                (baseline_source_accepted, "baseline source is not accepted evidence"),
                (baseline_complete, "baseline freeze contract is incomplete"),
                (
                    trace.decision != "GO"
                    or (
                        baseline is not None
                        and baseline.reproduced
                        and baseline.baseline_parity_verified is True
                    ),
                    "GO baseline is not reproduced with parity",
                ),
            ),
        ),
        _score_stage(
            "gap_hypothesis",
            (
                (
                    _hypothesis_complete(trace.hypothesis),
                    "falsifiable hypothesis is missing condition, limitation, mechanism, "
                    "intervention, metric, or guardrail",
                ),
            ),
        ),
        _score_stage(
            "module_compatibility",
            (
                (
                    modules_complete or module_defer_valid,
                    "module contracts are incomplete and design was not validly deferred",
                ),
                (
                    module_defer_valid
                    or all(item.role_compatible is True for item in trace.modules),
                    "one or more module roles are incompatible",
                ),
            ),
        ),
        _score_stage(
            "minimal_stitch",
            (
                (
                    module_defer_valid or 1 <= len(trace.modules) <= 2,
                    "minimal stitch must use one or two modules beyond the baseline",
                ),
                (
                    module_defer_valid or trace.stitch_order == module_ids,
                    "stitch order must add the declared modules one causal factor at a time",
                ),
                (
                    module_defer_valid
                    or all(_present(item.implementation_switch) for item in trace.modules),
                    "each module requires a disable switch for baseline parity",
                ),
            ),
        ),
        _score_stage(
            "experiment_matrix",
            (
                (experiments_complete, "experiment matrix fields are incomplete"),
                ("baseline" in experiment_arms, "baseline experiment arm is missing"),
                (
                    "strong_comparison" in experiment_arms,
                    "strong-comparison experiment arm is missing",
                ),
                (
                    module_defer_valid
                    or bool({"single_module", "full"} & experiment_arms),
                    "method experiment arm is missing",
                ),
                (bool(trace.stop_conditions), "stop conditions are missing"),
            ),
        ),
        _score_stage(
            "decision",
            (
                (
                    observed_decision == case.decision,
                    f"expected {case.decision}, observed {observed_decision}",
                ),
                (bool(trace.next_actions), "decision recovery path is missing"),
            ),
        ),
    )
    hard_failures = _hard_failures(trace)
    score = sum(item.earned for item in stages)
    decision_matches = observed_decision == case.decision
    status: Literal["passed", "failed"] = (
        "passed"
        if score >= minimum_score and decision_matches and not hard_failures
        else "failed"
    )
    return CaseEvaluation(
        case_id=case.case_id,
        status=status,
        score=score,
        minimum_score=minimum_score,
        expected_decision=case.decision,
        observed_decision=observed_decision,
        decision_matches=decision_matches,
        hard_failures=hard_failures,
        stages=stages,
        tags=case.tags,
    )


def evaluate_dataset(
    dataset: GoldDataset,
    traces: tuple[AcademicTailoringRunTrace, ...],
    *,
    minimum_score: int = 80,
) -> AggregateEvaluation:
    trace_ids = tuple(item.case_id for item in traces)
    if len(trace_ids) != len(set(trace_ids)):
        raise ValueError("candidate run contains duplicate case IDs")
    expected_ids = {item.case_id for item in dataset.cases}
    if set(trace_ids) != expected_ids:
        missing = sorted(expected_ids - set(trace_ids))
        extra = sorted(set(trace_ids) - expected_ids)
        raise ValueError(f"candidate run case identity mismatch: missing={missing}, extra={extra}")
    trace_by_id = {item.case_id: item for item in traces}
    results = tuple(
        evaluate_case(case, trace_by_id[case.case_id], minimum_score=minimum_score)
        for case in dataset.cases
    )
    by_tag: dict[str, dict[str, int]] = {}
    for result in results:
        for tag in result.tags:
            bucket = by_tag.setdefault(tag, {"total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            bucket[result.status] += 1
    passed = sum(item.status == "passed" for item in results)
    payload: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "dataset_digest": dataset.dataset_digest,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "average_score": round(sum(item.score for item in results) / len(results), 2),
        "decision_accuracy": round(
            sum(item.decision_matches for item in results) / len(results), 4
        ),
        "hard_failure_count": sum(len(item.hard_failures) for item in results),
        "by_tag": by_tag,
        "cases": [item.model_dump(mode="json") for item in results],
    }
    return AggregateEvaluation.model_validate(
        {**payload, "report_digest": _sha256(payload)}
    )


def _gold_review(
    case: GoldCase,
    index: int,
    role: EvidenceRole,
) -> EvidenceReview:
    return EvidenceReview(
        evidence_id=f"{case.case_id}-evidence-{index:02d}",
        source_type=(
            "user_material" if index <= len(case.supplied_materials) else "paper"
        ),
        identity_verified=True,
        relevance_reviewed=True,
        relevance_passed=True,
        accepted=True,
        role=role,
        gap_ids=(f"{case.case_id}-{role}",),
        claim_ids=(f"{case.case_id}-claim-{role}",),
        core_evidence=role in {"baseline", "gap", "parallel_method"},
        full_text_checked=True,
        source_is_supplied_material=index <= len(case.supplied_materials),
        role_compatible=True,
    )


def build_gold_self_check_trace(case: GoldCase) -> AcademicTailoringRunTrace:
    roles: tuple[EvidenceRole, ...] = (
        "baseline",
        "parallel_method",
        "gap",
        "strong_comparison",
        "risk",
    )
    reviews = tuple(_gold_review(case, index, role) for index, role in enumerate(roles, 1))
    baseline_candidates = case.baseline_expectation.get("candidate_families", [])
    baseline_name = (
        str(baseline_candidates[0])
        if isinstance(baseline_candidates, list) and baseline_candidates
        else "gold baseline candidate"
    )
    modules = tuple(
        ModuleTrace(
            module_id=f"module-{index}",
            evidence_id=reviews[index].evidence_id,
            original_role=str(expectation.get("role", "parallel method")),
            proposed_role=str(expectation.get("role", "parallel method")),
            input_semantics="gold-declared input semantics",
            output_semantics="gold-declared output semantics",
            input_shape="gold-declared input shape",
            output_shape="gold-declared output shape",
            optimization_interaction="isolated causal factor with matched budget",
            compute_cost="measured resource delta",
            failure_mode="gold-declared failure mode",
            implementation_switch=f"enable_module_{index}",
            role_compatible=True,
        )
        for index, expectation in enumerate(case.parallel_expectations[:2], start=1)
    )
    experiments = (
        ExperimentTrace(
            experiment_id="E0-baseline",
            arm_type="baseline",
            dataset="selected dataset",
            split="frozen split",
            preprocessing="matched preprocessing",
            tuning_budget="matched tuning budget",
            metrics=("primary metric",),
            seeds=(1, 2, 3),
            uncertainty_reporting="confidence interval",
            resource_measures=("latency", "memory"),
            stopping_criteria=case.stop_conditions[0],
        ),
        ExperimentTrace(
            experiment_id="E1-single-module",
            arm_type="single_module",
            included_modules=(modules[0].module_id,) if modules else (),
            dataset="selected dataset",
            split="frozen split",
            preprocessing="matched preprocessing",
            tuning_budget="matched tuning budget",
            metrics=("primary metric",),
            seeds=(1, 2, 3),
            uncertainty_reporting="confidence interval",
            resource_measures=("latency", "memory"),
            stopping_criteria=case.stop_conditions[0],
        ),
        ExperimentTrace(
            experiment_id="E2-strong-comparison",
            arm_type="strong_comparison",
            dataset="selected dataset",
            split="frozen split",
            preprocessing="matched preprocessing",
            tuning_budget="matched tuning budget",
            metrics=("primary metric",),
            seeds=(1, 2, 3),
            uncertainty_reporting="confidence interval",
            resource_measures=("latency", "memory"),
            stopping_criteria=case.stop_conditions[-1],
        ),
    )
    observed: ObservedDecision = "REVISE" if case.decision == "REVISE_TO_PILOT" else case.decision
    advice = case.tailoring_advice.get("recommended_stitch")
    next_action = str(advice) if advice else "execute the bounded recovery path"
    return AcademicTailoringRunTrace(
        case_id=case.case_id,
        fact_partitions=FactPartitions(
            verified=(case.user_input,),
            inferred=(f"normalized intent: {_canonical_json(case.intent)}",),
            proposed=(case.hypothesis,),
            unknown=case.unknowns,
        ),
        retrieval_roles=roles,
        evidence_reviews=reviews,
        clarification_questions=case.clarification_questions,
        resolved_unknowns=case.unknowns[:2],
        baseline=BaselineTrace(
            name=baseline_name,
            source_evidence_id=reviews[0].evidence_id,
            version_or_commit="must-be-frozen-before-execution",
            dataset="selected dataset",
            split="frozen split",
            metrics=("primary metric", "resource metric"),
            environment="recorded execution environment",
            seed_policy="at least three seeds where feasible",
            compute_assumptions="declared compute budget",
            disabled_module_parity_path="all modules disabled",
            baseline_parity_verified=False,
            reproduced=False,
            strong_comparisons=("gold strong comparison",),
        ),
        hypothesis=HypothesisTrace(
            condition=case.hypothesis,
            limitation=case.hypothesis,
            mechanism=case.hypothesis,
            intervention=case.hypothesis,
            target_metric=case.hypothesis,
            guardrail=case.stop_conditions[0],
        ),
        modules=modules,
        module_design_deferred=False,
        stitch_order=tuple(item.module_id for item in modules),
        experiments=experiments,
        decision=observed,
        pilot_recommended=case.decision == "REVISE_TO_PILOT",
        next_actions=(next_action,),
        stop_conditions=case.stop_conditions,
        stronger_baselines_considered=True,
        negative_results_visible=True,
        trace_audit_passed=True,
    )


def run_gold_self_check(root: Path, *, minimum_score: int = 80) -> AggregateEvaluation:
    dataset = load_gold_dataset(root)
    traces = tuple(build_gold_self_check_trace(case) for case in dataset.cases)
    return evaluate_dataset(dataset, traces, minimum_score=minimum_score)
