from __future__ import annotations

from pathlib import Path

import pytest

from paperagent.evaluation import (
    EvaluationCase,
    EvaluationObservation,
    build_report,
    grade_case,
    load_cases,
)


def test_load_seed_corpus() -> None:
    cases = load_cases(Path("evals/v0_6/cases.jsonl"))

    assert len(cases) == 4
    assert {case.category for case in cases} == {
        "in_domain",
        "ood",
        "insufficient_evidence",
        "adversarial",
    }


def test_grade_case_fails_when_cost_is_unknown() -> None:
    case = EvaluationCase(
        case_id="case-1",
        version="v0.6",
        category="in_domain",
        question="question",
        expected_terminal="succeeded",
        required_properties=("grounded",),
        forbidden_properties=("fabricated",),
        max_calls=2,
        max_cost_usd=0.1,
    )
    result = grade_case(
        case,
        EvaluationObservation(
            case_id="case-1",
            terminal="succeeded",
            observed_properties=("grounded",),
            calls=1,
        ),
    )

    assert result.passed is False
    assert result.cost_within_budget is None


def test_grade_case_passes_with_measured_cost() -> None:
    case = EvaluationCase(
        case_id="case-1",
        version="v0.6",
        category="in_domain",
        question="question",
        expected_terminal="succeeded",
        required_properties=("grounded",),
        max_calls=2,
        max_cost_usd=0.1,
    )

    result = grade_case(
        case,
        EvaluationObservation(
            case_id="case-1",
            terminal="succeeded",
            observed_properties=("grounded",),
            calls=1,
            estimated_cost_usd=0.01,
        ),
    )

    assert result.passed is True
    assert result.cost_within_budget is True


def test_report_keeps_missing_observations_visible() -> None:
    cases = (
        EvaluationCase(
            case_id="case-1",
            version="v0.6",
            category="ood",
            question="question",
            expected_terminal="succeeded",
            max_calls=1,
            max_cost_usd=0.1,
        ),
    )

    report = build_report(cases, ())

    assert report.total == 1
    assert report.failed == 1
    assert report.skipped == 1
    assert report.results[0].failure == "missing observation"


def test_report_rejects_duplicate_observations() -> None:
    cases = (
        EvaluationCase(
            case_id="case-1",
            version="v0.6",
            category="ood",
            question="question",
            expected_terminal="succeeded",
            max_calls=1,
            max_cost_usd=0.1,
        ),
    )
    observation = EvaluationObservation(
        case_id="case-1",
        terminal="succeeded",
        calls=1,
        estimated_cost_usd=0.01,
    )

    with pytest.raises(ValueError, match="duplicate observation"):
        build_report(cases, (observation, observation))
