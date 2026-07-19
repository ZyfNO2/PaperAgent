from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from paperagent.academic_tailoring import (
    EvidenceState,
    ResultStatus,
    TailoredResearchProposal,
    TailoringDecision,
    TailoringTask,
    compose_tailored_research_proposal,
)


class TailoringMutation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reproduced: bool | None = None
    clear_reproduced_metrics: bool = False
    evidence_state_overrides: dict[str, EvidenceState] = Field(default_factory=dict)
    license_overrides: dict[str, str] = Field(default_factory=dict)
    semantic_mapping_overrides: dict[str, str] = Field(default_factory=dict)
    adapter_overrides: dict[str, str] = Field(default_factory=dict)
    novelty_thesis: str | None = None
    why_not_simple_splice: str | None = None
    remove_module_sources: tuple[str, ...] = ()


class AcademicTailoringCaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    category: Literal[
        "happy_path",
        "reproduction_failure",
        "provenance_failure",
        "license_failure",
        "compatibility_failure",
        "novelty_failure",
        "insufficient_evidence",
        "multilingual",
    ]
    description: str = Field(min_length=1)
    mutation: TailoringMutation = Field(default_factory=TailoringMutation)
    expected_decision: TailoringDecision
    minimum_score: int = Field(ge=0, le=100, default=85)


class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    earned: int
    available: int
    findings: tuple[str, ...] = ()


class AcademicTailoringGrade(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    category: str
    expected_decision: TailoringDecision
    observed_decision: TailoringDecision
    decision_matches: bool
    score: int
    minimum_score: int
    passed: bool
    hard_blockers: tuple[str, ...]
    dimensions: tuple[DimensionScore, ...]


class AcademicTailoringEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_digest: str
    total: int
    passed: int
    failed: int
    by_category: dict[str, dict[str, int]]
    grades: tuple[AcademicTailoringGrade, ...]


def load_base_task(path: Path) -> TailoringTask:
    return TailoringTask.model_validate_json(path.read_text(encoding="utf-8"))


def load_case_specs(path: Path) -> tuple[AcademicTailoringCaseSpec, ...]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("academic tailoring case manifest must be a non-empty JSON array")
    specs = tuple(AcademicTailoringCaseSpec.model_validate(item) for item in parsed)
    identifiers = tuple(spec.case_id for spec in specs)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate academic tailoring evaluation case ID")
    return specs


def materialize_task(base: TailoringTask, mutation: TailoringMutation) -> TailoringTask:
    payload = base.model_dump(mode="json")
    reproduction = cast(dict[str, Any], payload["reproduction"])
    if mutation.reproduced is not None:
        reproduction["reproduced"] = mutation.reproduced
    if mutation.clear_reproduced_metrics:
        reproduction["reproduced_metrics"] = {}

    papers = cast(list[dict[str, Any]], payload["papers"])
    for paper in papers:
        paper_id = cast(str, paper["paper_id"])
        if paper_id in mutation.evidence_state_overrides:
            paper["evidence_state"] = mutation.evidence_state_overrides[paper_id].value
        if paper_id in mutation.license_overrides:
            paper["license"] = mutation.license_overrides[paper_id]
    if mutation.remove_module_sources:
        removed = set(mutation.remove_module_sources)
        payload["papers"] = [paper for paper in papers if paper["paper_id"] not in removed]

    intents = cast(list[dict[str, Any]], payload["module_intents"])
    for intent in intents:
        source_id = cast(str, intent["source_paper_id"])
        if source_id in mutation.semantic_mapping_overrides:
            intent["semantic_mapping"] = mutation.semantic_mapping_overrides[source_id]
        if source_id in mutation.adapter_overrides:
            intent["adapter"] = mutation.adapter_overrides[source_id]

    if mutation.novelty_thesis is not None:
        payload["novelty_thesis"] = mutation.novelty_thesis
    if mutation.why_not_simple_splice is not None:
        payload["why_not_simple_splice"] = mutation.why_not_simple_splice
    return TailoringTask.model_validate(payload)


def _score(
    name: str, available: int, checks: tuple[bool, ...], findings: list[str]
) -> DimensionScore:
    earned = available if not checks else round(available * sum(checks) / len(checks))
    return DimensionScore(
        name=name,
        earned=earned,
        available=available,
        findings=tuple(findings),
    )


def grade_proposal(
    spec: AcademicTailoringCaseSpec,
    task: TailoringTask,
    proposal: TailoredResearchProposal,
) -> AcademicTailoringGrade:
    dimensions: list[DimensionScore] = []
    hard_blockers: list[str] = []

    decision_matches = proposal.decision is spec.expected_decision
    dimensions.append(
        DimensionScore(
            name="decision_correctness",
            earned=15 if decision_matches else 0,
            available=15,
            findings=() if decision_matches else ("GO/REVISE/NO_GO decision does not match",),
        )
    )

    expected_reference_ids = {
        task.reproduction.baseline_paper_id,
        *(intent.source_paper_id for intent in task.module_intents),
    }
    references = {reference.paper_id: reference for reference in proposal.references}
    provenance_checks: list[bool] = []
    provenance_findings: list[str] = []
    for paper_id in sorted(expected_reference_ids):
        reference = references.get(paper_id)
        present = reference is not None
        provenance_checks.append(present)
        if not present:
            provenance_findings.append(f"missing reference card for {paper_id}")
            hard_blockers.append(f"missing attribution for {paper_id}")
            continue
        assert reference is not None
        complete = all(
            (
                bool(reference.title.strip()),
                bool(reference.stable_identifier.strip()),
                bool(reference.method_used.strip()),
                bool(reference.borrowed_component.strip()),
                bool(reference.license.strip()),
            )
        )
        provenance_checks.append(complete)
        if not complete:
            provenance_findings.append(f"incomplete method attribution for {paper_id}")
    dimensions.append(
        _score("provenance_and_attribution", 15, tuple(provenance_checks), provenance_findings)
    )

    baseline_checks = (
        proposal.baseline.paper_id == task.reproduction.baseline_paper_id,
        proposal.baseline.implementation_ref == task.reproduction.implementation_ref,
        proposal.baseline.dataset == task.reproduction.dataset,
        proposal.baseline.split == task.reproduction.split,
        proposal.baseline.seed_policy == task.reproduction.seed_policy,
        proposal.baseline.reproduced == task.reproduction.reproduced,
        proposal.baseline.reproduced_metrics == task.reproduction.reproduced_metrics,
    )
    baseline_findings = [] if all(baseline_checks) else ["baseline reproduction record drifted"]
    dimensions.append(_score("baseline_reproduction", 10, baseline_checks, baseline_findings))

    paper_methods = {paper.paper_id: paper.method_name for paper in task.papers}
    modules_by_source = {module.source_paper_id: module for module in proposal.modules}
    trace_checks: list[bool] = []
    trace_findings: list[str] = []
    for intent in task.module_intents:
        module = modules_by_source.get(intent.source_paper_id)
        present = module is not None
        trace_checks.append(present)
        if not present:
            trace_findings.append(f"missing module extracted from {intent.source_paper_id}")
            continue
        assert module is not None
        method_matches = module.method_used == paper_methods.get(intent.source_paper_id)
        trace_checks.extend(
            (
                method_matches,
                module.insertion_point == intent.insertion_point,
                module.proposed_role == intent.proposed_role,
                bool(module.borrowed_component.strip()),
            )
        )
        if not method_matches:
            trace_findings.append(f"method name drift for {intent.source_paper_id}")
    dimensions.append(_score("module_method_traceability", 10, tuple(trace_checks), trace_findings))

    compatibility_checks: list[bool] = []
    compatibility_findings: list[str] = []
    for intent in task.module_intents:
        module = modules_by_source.get(intent.source_paper_id)
        if module is None:
            compatibility_checks.append(False)
            continue
        invalid = intent.semantic_mapping.strip().lower() in {
            "shape-only",
            "shape only",
            "same shape",
            "reshape",
            "projection only",
            "tensor",
        } or intent.adapter.strip().lower() in {
            "shape-only",
            "shape only",
            "same shape",
            "reshape",
            "projection only",
            "tensor",
        }
        expected_status = "blocked" if invalid else "compatible"
        status_matches = module.compatibility_status == expected_status
        compatibility_checks.extend(
            (
                status_matches,
                bool(module.semantic_mapping.strip()),
                bool(module.failure_mode.strip()),
                bool(module.compatibility_reason.strip()),
            )
        )
        if not status_matches:
            compatibility_findings.append(
                f"compatibility status for {intent.source_paper_id} should be {expected_status}"
            )
    dimensions.append(
        _score("semantic_compatibility", 10, tuple(compatibility_checks), compatibility_findings)
    )

    innovation = proposal.innovation_points[0] if proposal.innovation_points else None
    innovation_checks = (
        innovation is not None,
        innovation is not None and bool(innovation.contribution.strip()),
        innovation is not None and bool(innovation.why_not_simple_splice.strip()),
        innovation is not None and bool(innovation.falsifiable_test.strip()),
        innovation is not None and innovation.status == "proposed",
    )
    innovation_findings = (
        [] if all(innovation_checks) else ["innovation is not explicit and falsifiable"]
    )
    dimensions.append(_score("innovation_distinctness", 15, innovation_checks, innovation_findings))

    story = proposal.academic_story
    story_checks = tuple(
        bool(value.strip())
        for value in (
            story.problem,
            story.baseline_evidence,
            story.gap,
            story.mechanism,
            story.intervention,
            story.expected_observation,
            story.implication,
        )
    )
    dimensions.append(
        _score(
            "academic_story_coherence",
            10,
            story_checks,
            [] if all(story_checks) else ["academic story has an empty causal step"],
        )
    )

    module_ids = {module.module_id for module in proposal.modules}
    baseline_arms = [arm for arm in proposal.experiment_matrix if arm.arm_type == "baseline"]
    full_arms = [arm for arm in proposal.experiment_matrix if arm.arm_type == "full"]
    single_covered = {
        module_id
        for arm in proposal.experiment_matrix
        if arm.arm_type == "single_module" and len(arm.included_modules) == 1
        for module_id in arm.included_modules
    }
    leave_one_out_count = sum(arm.arm_type == "leave_one_out" for arm in proposal.experiment_matrix)
    fair_fields = all(
        arm.dataset == task.reproduction.dataset
        and arm.split == task.reproduction.split
        and arm.preprocessing == task.preprocessing
        and arm.tuning_budget == task.tuning_budget
        and arm.seeds == task.seeds
        for arm in proposal.experiment_matrix
    )
    experiment_checks = (
        len(baseline_arms) == 1 and not baseline_arms[0].included_modules,
        len(full_arms) == 1 and set(full_arms[0].included_modules) == module_ids,
        single_covered == module_ids,
        len(module_ids) <= 1 or leave_one_out_count == len(module_ids),
        fair_fields,
    )
    dimensions.append(
        _score(
            "fair_experiment_and_ablation",
            10,
            experiment_checks,
            [] if all(experiment_checks) else ["experiment matrix is incomplete or unfair"],
        )
    )

    result_by_metric = {item.metric: item for item in proposal.expected_results}
    result_checks: list[bool] = []
    result_findings: list[str] = []
    for target in task.expected_results:
        observed = result_by_metric.get(target.metric)
        present = observed is not None
        result_checks.append(present)
        if not present:
            result_findings.append(f"missing expected result for {target.metric}")
            continue
        assert observed is not None
        honest = observed.status is ResultStatus.PROPOSED and observed.evidence_id is None
        result_checks.extend(
            (
                observed.baseline_value == target.baseline_value,
                observed.target_value == target.target_value,
                observed.direction is target.direction,
                observed.guardrail == target.guardrail,
                honest,
            )
        )
        if not honest:
            hard_blockers.append(f"unverified result for {target.metric} is presented as observed")
    dimensions.append(_score("expected_result_honesty", 5, tuple(result_checks), result_findings))

    task_requires_no_go = (
        not task.reproduction.reproduced
        or not task.reproduction.reproduced_metrics
        or any(paper.evidence_state is EvidenceState.UNVERIFIED for paper in task.papers)
        or any(
            paper.license.strip().lower()
            in {"unknown", "missing", "unverified", "incompatible", "proprietary-no-reuse"}
            for paper in task.papers
        )
        or any(module.compatibility_status == "blocked" for module in proposal.modules)
        or bool(proposal.blockers)
    )
    if proposal.decision is TailoringDecision.GO and task_requires_no_go:
        hard_blockers.append("proposal claims GO despite a release-blocking research condition")

    score = sum(item.earned for item in dimensions)
    passed = decision_matches and score >= spec.minimum_score and not hard_blockers
    return AcademicTailoringGrade(
        case_id=spec.case_id,
        category=spec.category,
        expected_decision=spec.expected_decision,
        observed_decision=proposal.decision,
        decision_matches=decision_matches,
        score=score,
        minimum_score=spec.minimum_score,
        passed=passed,
        hard_blockers=tuple(sorted(set(hard_blockers))),
        dimensions=tuple(dimensions),
    )


def corpus_digest(base: TailoringTask, specs: tuple[AcademicTailoringCaseSpec, ...]) -> str:
    payload = {
        "base": base.model_dump(mode="json"),
        "cases": [spec.model_dump(mode="json") for spec in specs],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_corpus(
    base: TailoringTask,
    specs: tuple[AcademicTailoringCaseSpec, ...],
) -> tuple[
    AcademicTailoringEvaluationReport,
    tuple[TailoringTask, ...],
    tuple[TailoredResearchProposal, ...],
]:
    tasks: list[TailoringTask] = []
    proposals: list[TailoredResearchProposal] = []
    grades: list[AcademicTailoringGrade] = []
    for spec in specs:
        task = materialize_task(base, spec.mutation)
        proposal = compose_tailored_research_proposal(task)
        grade = grade_proposal(spec, task, proposal)
        tasks.append(task)
        proposals.append(proposal)
        grades.append(grade)

    counts: dict[str, Counter[str]] = {}
    for grade in grades:
        counter = counts.setdefault(grade.category, Counter())
        counter["total"] += 1
        counter["passed" if grade.passed else "failed"] += 1
    report = AcademicTailoringEvaluationReport(
        corpus_digest=corpus_digest(base, specs),
        total=len(grades),
        passed=sum(item.passed for item in grades),
        failed=sum(not item.passed for item in grades),
        by_category={category: dict(counter) for category, counter in sorted(counts.items())},
        grades=tuple(grades),
    )
    return report, tuple(tasks), tuple(proposals)
