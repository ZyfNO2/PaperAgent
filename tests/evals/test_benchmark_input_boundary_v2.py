from __future__ import annotations

import inspect
from typing import Any, cast

import pytest
from pydantic import ValidationError

from paperagent import claw_benchmark_runtime as runtime_module
from paperagent.benchmark_input import BenchmarkInput, benchmark_input_to_request
from paperagent.providers import LLMProvider, SearchProvider
from paperagent.state import PaperAgentState


class _CapturingGraph:
    def __init__(self) -> None:
        self.initial_state: dict[str, Any] | None = None
        self.config: dict[str, Any] | None = None
        self.stream_mode: str | None = None

    async def astream(
        self,
        initial_state: dict[str, Any],
        config: dict[str, Any],
        *,
        stream_mode: str,
    ) -> Any:
        self.initial_state = initial_state
        self.config = config
        self.stream_mode = stream_mode
        yield cast(PaperAgentState, {"request": initial_state["request"]})


def _input() -> BenchmarkInput:
    return BenchmarkInput(
        user_input="Design an evidence-backed method under the stated constraints.",
        supplied_material_titles=("Reference A", "Reference B"),
        user_declared_roles=("baseline", "mechanism"),
        declared_constraints=("single accelerator", "fixed evaluation split"),
    )


def test_declared_constraints_are_part_of_user_visible_request() -> None:
    request = benchmark_input_to_request(_input())
    assert request.question.startswith("Design an evidence-backed method")
    assert request.required_constraints == [
        "single accelerator",
        "fixed evaluation split",
    ]
    assert request.user_material_refs == [
        "Reference A [declared role: baseline]",
        "Reference B [declared role: mechanism]",
    ]


def test_benchmark_input_rejects_external_evaluation_fields() -> None:
    payload = _input().model_dump()
    payload["case_id"] = "external-case"
    payload["oracle"] = {"accepted_decisions": ["REVISE"]}
    payload["metadata"] = {"split": "development"}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BenchmarkInput.model_validate(payload)


def test_input_only_executor_signature_excludes_external_fields() -> None:
    parameters = inspect.signature(runtime_module.execute_benchmark_input).parameters
    assert "benchmark_input" in parameters
    assert "case_id" not in parameters
    assert "oracle" not in parameters
    assert "metadata" not in parameters
    assert "scoring" not in parameters
    assert "metamorphic_group" not in parameters


@pytest.mark.asyncio
async def test_input_only_executor_projects_only_user_visible_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _CapturingGraph()
    monkeypatch.setattr(runtime_module, "build_graph", lambda: graph)
    monkeypatch.setattr(
        runtime_module,
        "state_to_primitive",
        lambda state: {"request": state["request"].model_dump(mode="json")},
    )

    primitive, state = await runtime_module.execute_benchmark_input(
        benchmark_input=_input(),
        llm=cast(LLMProvider, object()),
        search=cast(SearchProvider, object()),
        max_llm_calls=3,
        task_id="runtime-task",
    )

    assert graph.initial_state is not None
    request = graph.initial_state["request"]
    assert request.question == _input().user_input
    assert request.required_constraints == list(_input().declared_constraints)
    assert request.user_material_refs == [
        "Reference A [declared role: baseline]",
        "Reference B [declared role: mechanism]",
    ]
    assert graph.stream_mode == "values"
    assert graph.config is not None
    assert graph.config["configurable"]["thread_id"] == "runtime-task"
    assert "case_id" not in repr(graph.initial_state)
    assert "oracle" not in repr(graph.initial_state)
    assert "metadata" not in repr(graph.initial_state)
    assert state["request"] == request
    assert primitive["request"]["required_constraints"] == [
        "single accelerator",
        "fixed evaluation split",
    ]


@pytest.mark.asyncio
async def test_input_only_executor_fails_closed_when_graph_emits_no_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyGraph:
        async def astream(self, *args: Any, **kwargs: Any) -> Any:
            if False:
                yield None

    monkeypatch.setattr(runtime_module, "build_graph", _EmptyGraph)

    with pytest.raises(RuntimeError, match="emitted no state"):
        await runtime_module.execute_benchmark_input(
            benchmark_input=_input(),
            llm=cast(LLMProvider, object()),
            search=cast(SearchProvider, object()),
            max_llm_calls=3,
            task_id="runtime-task",
        )
