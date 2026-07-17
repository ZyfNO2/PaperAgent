from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    category: Literal["in_domain", "ood", "insufficient_evidence", "adversarial"]
    question: str = Field(min_length=1)
    expected_terminal: str = Field(min_length=1)
    required_properties: tuple[str, ...] = ()
    forbidden_properties: tuple[str, ...] = ()
    max_calls: int = Field(ge=1)
    max_cost_usd: float = Field(gt=0)


class EvaluationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    terminal: str
    observed_properties: tuple[str, ...] = ()
    calls: int = Field(ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    skipped: bool = False
    failure: str | None = None


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    category: str
    passed: bool
    missing_required: tuple[str, ...]
    observed_forbidden: tuple[str, ...]
    terminal_matches: bool
    calls_within_budget: bool
    cost_within_budget: bool | None
    skipped: bool
    failure: str | None


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_digest: str
    total: int
    passed: int
    failed: int
    skipped: int
    by_category: dict[str, dict[str, int]]
    results: tuple[EvaluationResult, ...]


def load_cases(path: Path) -> tuple[EvaluationCase, ...]:
    cases: list[EvaluationCase] = []
    identifiers: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = EvaluationCase.model_validate_json(line)
        if case.case_id in identifiers:
            raise ValueError(f"duplicate evaluation case ID at line {line_number}: {case.case_id}")
        identifiers.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError("evaluation corpus is empty")
    return tuple(cases)


def corpus_digest(cases: tuple[EvaluationCase, ...]) -> str:
    canonical = [case.model_dump(mode="json") for case in cases]
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def grade_case(case: EvaluationCase, observation: EvaluationObservation) -> EvaluationResult:
    if observation.case_id != case.case_id:
        raise ValueError("observation case ID does not match evaluation case")
    observed = set(observation.observed_properties)
    missing_required = tuple(sorted(set(case.required_properties) - observed))
    observed_forbidden = tuple(sorted(set(case.forbidden_properties) & observed))
    terminal_matches = observation.terminal == case.expected_terminal
    calls_within_budget = observation.calls <= case.max_calls
    cost_within_budget = (
        None
        if observation.estimated_cost_usd is None
        else observation.estimated_cost_usd <= case.max_cost_usd
    )
    passed = (
        not observation.skipped
        and observation.failure is None
        and not missing_required
        and not observed_forbidden
        and terminal_matches
        and calls_within_budget
        and cost_within_budget is not False
    )
    return EvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=passed,
        missing_required=missing_required,
        observed_forbidden=observed_forbidden,
        terminal_matches=terminal_matches,
        calls_within_budget=calls_within_budget,
        cost_within_budget=cost_within_budget,
        skipped=observation.skipped,
        failure=observation.failure,
    )


def build_report(
    cases: tuple[EvaluationCase, ...],
    observations: tuple[EvaluationObservation, ...],
) -> EvaluationReport:
    by_id = {case.case_id: case for case in cases}
    observation_ids = {observation.case_id for observation in observations}
    unknown = observation_ids - set(by_id)
    if unknown:
        raise ValueError(f"observations contain unknown case IDs: {sorted(unknown)}")

    results: list[EvaluationResult] = []
    for case in cases:
        observation = next(
            (item for item in observations if item.case_id == case.case_id),
            EvaluationObservation(
                case_id=case.case_id,
                terminal="missing",
                skipped=True,
                calls=0,
                failure="missing observation",
            ),
        )
        results.append(grade_case(case, observation))

    counts: dict[str, Counter[str]] = {}
    for result in results:
        counter = counts.setdefault(result.category, Counter())
        counter["total"] += 1
        counter["passed" if result.passed else "failed"] += 1
        if result.skipped:
            counter["skipped"] += 1

    return EvaluationReport(
        corpus_digest=corpus_digest(cases),
        total=len(results),
        passed=sum(result.passed for result in results),
        failed=sum(not result.passed for result in results),
        skipped=sum(result.skipped for result in results),
        by_category={category: dict(counter) for category, counter in sorted(counts.items())},
        results=tuple(results),
    )
