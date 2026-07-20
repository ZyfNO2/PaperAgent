from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from paperagent.api.real_executor import SystemClock, UUIDIdFactory
from paperagent.benchmark_input import BenchmarkInput, benchmark_input_to_request
from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary
from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace
from paperagent.claw_benchmark_normalizer import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.graph import build_graph
from paperagent.literature.factory import (
    LiteratureProviderSettings,
    build_literature_runtime,
)
from paperagent.persistence import InMemoryStateStore
from paperagent.providers import LLMProvider, SearchProvider
from paperagent.runtime import RuntimeServices
from paperagent.schemas import RunBudgets
from paperagent.state import PaperAgentState, state_to_primitive

SearchMode = Literal["fake", "literature"]


class BenchmarkSearchRuntime(Protocol):
    @property
    def adapter(self) -> SearchProvider: ...

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
        return build_literature_runtime(settings or LiteratureProviderSettings())
    raise ValueError(f"unsupported benchmark search mode: {mode}")


def _structured_pilot_recommendation(state: PaperAgentState) -> bool:
    """Derive pilot routing only from production structured state.

    Free-text next actions, clarification wording, supplied-paper titles, and benchmark
    annotations are deliberately excluded. A bounded pilot is recommended only when the
    completed outcome explicitly routes a REVISE verdict through method repair and a
    concrete method artifact exists to test.
    """

    outcome = state.get("final_outcome")
    method = state.get("method")
    return bool(
        outcome is not None
        and outcome.scientific_verdict == "REVISE"
        and outcome.quality_route == "repair_method"
        and method is not None
    )


async def execute_benchmark_case(
    *,
    benchmark_input: BenchmarkInput,
    case_id: str,
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
        {"request": benchmark_input_to_request(benchmark_input)},
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
        raise RuntimeError(f"benchmark case {case_id} emitted no state")

    leakage_audit = audit_benchmark_execution_boundary()
    primitive = state_to_primitive(latest)
    trace = normalize_paperagent_state(
        latest,
        BenchmarkNormalizationContext(
            case_id=case_id,
            pilot_recommended=_structured_pilot_recommendation(latest),
            future_or_test_leakage=not leakage_audit.passed,
            leakage_findings=leakage_audit.findings,
        ),
    )
    return primitive, trace


__all__ = [
    "BenchmarkSearchRuntime",
    "SearchMode",
    "build_benchmark_search_runtime",
    "execute_benchmark_case",
]
