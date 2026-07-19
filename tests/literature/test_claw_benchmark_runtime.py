from __future__ import annotations

import pytest

from paperagent.claw_academic_benchmark import GoldCase, SpecialAssertions, SuppliedMaterial
from paperagent.claw_benchmark_runtime import (
    build_benchmark_search_runtime,
    case_to_request,
)
from paperagent.providers import FakeSearchProvider


def _case() -> GoldCase:
    return GoldCase(
        case_id="at-999-runtime-test",
        user_input="test research question",
        supplied_materials=(
            SuppliedMaterial(count=1, declared_role="baseline", title="Supplied paper"),
        ),
        intent={"task": "test"},
        unknowns=("dataset",),
        clarification_questions=("Which dataset?",),
        baseline_expectation={"candidate_families": ["baseline"]},
        parallel_expectations=({"role": "module"},),
        hypothesis="test hypothesis",
        tailoring_advice={"recommended_stitch": "pilot"},
        experiment_plan=("E0",),
        stop_conditions=("stop",),
        decision="REVISE_TO_PILOT",
        special_assertions=SpecialAssertions(required=("grounded",), forbidden=("fabricate",)),
        tags=("test",),
        trace_profile="academic-tailoring-gold-trace-v1",
    )


def test_fake_mode_requires_explicit_fixture_provider() -> None:
    with pytest.raises(ValueError, match="explicit fixture"):
        build_benchmark_search_runtime("fake")


def test_fake_mode_preserves_injected_provider() -> None:
    provider = FakeSearchProvider(fixtures={})
    runtime = build_benchmark_search_runtime("fake", fake_provider=provider)
    assert runtime.adapter is provider


def test_case_conversion_uses_only_user_input_and_supplied_materials() -> None:
    request = case_to_request(_case())
    assert request.question == "test research question"
    assert request.user_material_refs == ["Supplied paper [declared role: baseline]"]
    assert request.clarification_answer is None
