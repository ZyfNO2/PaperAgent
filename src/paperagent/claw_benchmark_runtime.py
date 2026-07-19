from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from paperagent.api.real_executor import SystemClock, UUIDIdFactory
from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace, GoldCase
from paperagent.claw_benchmark_adapter import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.graph import build_graph
from paperagent.literature.factory import (
    LiteratureProviderSettings,
    LiteratureRuntime,
    build_literature_runtime,
)
from paperagent.persistence import InMemoryStateStore
from paperagent.providers import LLMProvider, SearchProvider
from paperagent.runtime import RuntimeServices
from paperagent.schemas import RunBudgets
from paperagent.schemas.request import ResearchRequest
from paperagent.state import PaperAgentState, state_to_primitive

SearchMode = Literal["fake", "literature"]


class BenchmarkSearchRuntime(Protocol):
    adapter: SearchProvider

    async def aclose(self) -> None: ...


@dataclass(frozen=True)
class _InjectedSearchRuntime:
    adapter: SearchProvider

    async def aclose(self) -> None:
        return None


def build_benchmark_search_runtime(
    mode: SearchMode,
    *,
    settings: LiteratureProviderSettings | None = None,
    fake_provider: SearchProvider | None = None,
) -> BenchmarkSearchRuntime:
    """Build the benchmark search seam without silently substituting empty evidence.

    ``fake`` is deliberately injection-only: CI must provide an explicit deterministic
    fixture provider. ``literature`` reuses the production Literature Runtime.
    """

    if mode == "fake":
        if fake_provider is None:
            raise ValueError("fake benchmark mode requires an explicit fixture search provider")
        return _InjectedSearchRuntime(adapter=fake_provider)
    if mode == "literature":
        return cast(
            LiteratureRuntime,
            build_literature_runtime(settings or LiteratureProviderSettings()),
        )
    raise ValueError(f"unsupported benchmark search mode: {mode}")


def case_to_request(case: GoldCase) -> ResearchRequest:
    material_refs = [
        f"{material.title} [declared role: {material.declared_role}]"
        for material in case.supplied_materials
    ]
    return ResearchRequest(
        question=case.user_input,
        user_material_refs=material_refs,
    )


async def execute_benchmark_case(
    *,
    case: GoldCase,
    llm: LLMProvider,
    search: SearchProvider,
    max_llm_calls: int,
    task_id: str,
) -> tuple[dict[str, Any], AcademicTailoringRunTrace]:
    services = RuntimeServices(
        llm=llm,
        search=search,
        clock=SystemClock(),
        ids=UUIDIdFactory(),
        store=InMemoryStateStore(),
    )
    graph = build_graph()
    stream = graph.astream(
        {"request": case_to_request(case)},
        {
            "configurable": {
                "services": services,
                "thread_id": task_id,
                "network_policy": "allow_search",
                "budgets": RunBudgets(max_llm_calls=max_llm_calls),
                "human_review_policy": "block",
            }
        },
        stream_mode="values",
    )
    latest: PaperAgentState | None = None
    async for raw_state in stream:
        if isinstance(raw_state, Mapping):
            latest = cast(PaperAgentState, raw_state)
    if latest is None:
        raise RuntimeError(f"benchmark case {case.case_id} emitted no state")
    primitive = state_to_primitive(latest)
    trace = normalize_paperagent_state(
        latest,
        BenchmarkNormalizationContext(case_id=case.case_id),
    )
    return primitive, trace


__all__ = [
    "BenchmarkSearchRuntime",
    "SearchMode",
    "build_benchmark_search_runtime",
    "case_to_request",
    "execute_benchmark_case",
]
