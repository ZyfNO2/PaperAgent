from __future__ import annotations

import inspect

import pytest

from paperagent.benchmark_input import BenchmarkInput, benchmark_input_to_request
from paperagent.claw_academic_benchmark import GoldCase, SpecialAssertions, SuppliedMaterial
from paperagent.claw_benchmark_runtime import build_benchmark_search_runtime, execute_benchmark_case
from paperagent.claw_gold_adapter import benchmark_input_from_gold
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


def test_gold_projection_uses_only_user_visible_input() -> None:
    benchmark_input = benchmark_input_from_gold(_case())
    assert benchmark_input == BenchmarkInput(
        user_input="test research question",
        supplied_material_titles=("Supplied paper",),
        user_declared_roles=("baseline",),
    )
    request = benchmark_input_to_request(benchmark_input)
    assert request.question == "test research question"
    assert request.user_material_refs == ["Supplied paper [declared role: baseline]"]
    assert request.clarification_answer is None


def test_gold_only_mutations_do_not_change_executor_input() -> None:
    original = _case()
    mutated = original.model_copy(
        update={
            "decision": "NO_GO",
            "hypothesis": "completely different hidden hypothesis",
            "baseline_expectation": {"candidate_families": ["hidden-other"]},
            "parallel_expectations": ({"role": "hidden-other"},),
            "experiment_plan": ("hidden experiment",),
            "stop_conditions": ("hidden stop",),
        }
    )
    assert benchmark_input_from_gold(original) == benchmark_input_from_gold(mutated)


def test_executor_signature_cannot_receive_gold_case() -> None:
    parameters = inspect.signature(execute_benchmark_case).parameters
    assert "case" not in parameters
    assert tuple(parameters) == (
        "benchmark_input",
        "case_id",
        "llm",
        "search",
        "max_llm_calls",
        "task_id",
    )
