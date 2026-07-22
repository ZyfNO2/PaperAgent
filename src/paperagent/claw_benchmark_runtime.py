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
from paperagent.literature.factory import LiteratureProviderSettings, build_literature_runtime
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
    if mode == "fake":
        if fake_provider is None:
            raise ValueError("fake benchmark mode requires an explicit fixture search provider")
        return _InjectedSearchRuntime(adapter=fake_provider)
    if mode == "literature":
        return build_literature_runtime(settings or LiteratureProviderSettings())
    raise ValueError(f"unsupported benchmark search mode: {mode}")


async def execute_benchmark_input(
    *,
    benchmark_input: BenchmarkInput,
    llm: LLMProvider,
    search: SearchProvider,
    max_llm_calls: int,
    task_id: str,
    max_retrieval_rounds: int = 2,
    max_queries_per_round: int = 5,
    max_method_repairs: int = 1,
    max_evidence_items: int = 30,
    recursion_limit: int = 100,
) -> tuple[dict[str, Any], PaperAgentState]:
    """Execute only user-visible benchmark input through the production graph.

    Case identifiers, oracle fields, metadata, scoring rules, and metamorphic-group
    identifiers are intentionally absent from this function's signature and graph
    configuration. External evaluation may attach those fields only after execution.
    """

    if recursion_limit < 1:
        raise ValueError("recursion_limit must be positive")

    services = RuntimeServices(
        llm=llm,
        search=search,
        clock=SystemClock(),
        ids=UUIDIdFactory(),
        store=InMemoryStateStore(),
    )
    budgets = RunBudgets(
        max_llm_calls=max_llm_calls,
        max_retrieval_rounds=max_retrieval_rounds,
        max_queries_per_round=max_queries_per_round,
        max_method_repairs=max_method_repairs,
        max_evidence_items=max_evidence_items,
    )
    graph = build_graph()
    stream = graph.astream(
        {"request": benchmark_input_to_request(benchmark_input)},
        {
            "configurable": {
                "services": services,
                "thread_id": task_id,
                "network_policy": "allow_search",
                "budgets": budgets,
                "human_review_policy": "block",
            },
            "recursion_limit": recursion_limit,
        },
        stream_mode="values",
    )
    latest: PaperAgentState | None = None
    async for raw_state in stream:
        if isinstance(raw_state, Mapping):
            latest = cast(PaperAgentState, raw_state)
    if latest is None:
        raise RuntimeError("benchmark input execution emitted no state")
    return state_to_primitive(latest), latest


async def execute_benchmark_case(
    *,
    benchmark_input: BenchmarkInput,
    case_id: str,
    llm: LLMProvider,
    search: SearchProvider,
    max_llm_calls: int,
    task_id: str,
    max_retrieval_rounds: int = 2,
    max_queries_per_round: int = 5,
    max_method_repairs: int = 1,
    max_evidence_items: int = 30,
    recursion_limit: int = 100,
) -> tuple[dict[str, Any], AcademicTailoringRunTrace]:
    """Execute clean input first, then attach external case metadata for scoring."""

    primitive, latest = await execute_benchmark_input(
        benchmark_input=benchmark_input,
        llm=llm,
        search=search,
        max_llm_calls=max_llm_calls,
        task_id=task_id,
        max_retrieval_rounds=max_retrieval_rounds,
        max_queries_per_round=max_queries_per_round,
        max_method_repairs=max_method_repairs,
        max_evidence_items=max_evidence_items,
        recursion_limit=recursion_limit,
    )
    leakage_audit = audit_benchmark_execution_boundary()
    trace = normalize_paperagent_state(
        latest,
        BenchmarkNormalizationContext(
            case_id=case_id,
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
    "execute_benchmark_input",
]
