from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from paperagent.api.executor import (
    CancellationProbe,
    EventEmitter,
    LangGraphTaskExecutor,
    TaskExecutor,
)
from paperagent.api.models import JsonObject
from paperagent.graph import build_graph
from paperagent.literature.factory import (
    LiteratureProviderSettings,
    build_literature_runtime,
)
from paperagent.persistence import InMemoryStateStore
from paperagent.pricing import PriceTable
from paperagent.providers import LLMProvider, build_llm_provider
from paperagent.providers.runtime import ProviderRuntimeConfig, TelemetrySink
from paperagent.runtime import RuntimeServices
from paperagent.schemas import RunBudgets
from paperagent.schemas.request import ResearchRequest
from paperagent.testing import Clock, IdFactory


class SearchRuntime(Protocol):
    adapter: Any

    async def aclose(self) -> None: ...


ProviderBuilder = Callable[[ProviderRuntimeConfig, PriceTable | None], LLMProvider]
LiteratureBuilder = Callable[[LiteratureProviderSettings], SearchRuntime]


def _build_literature(settings: LiteratureProviderSettings) -> SearchRuntime:
    return build_literature_runtime(settings)


@dataclass(frozen=True)
class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(tz=UTC)


@dataclass(frozen=True)
class UUIDIdFactory(IdFactory):
    def new_id(self, namespace: str) -> str:
        return f"{namespace}_{uuid4().hex}"


@dataclass(frozen=True)
class RealTaskExecutor(TaskExecutor):
    provider_config: ProviderRuntimeConfig
    literature_settings: LiteratureProviderSettings = field(
        default_factory=LiteratureProviderSettings
    )
    price_table: PriceTable | None = None
    graph: Any = field(default_factory=build_graph)
    provider_builder: ProviderBuilder = build_llm_provider
    literature_builder: LiteratureBuilder = _build_literature

    def __post_init__(self) -> None:
        maximum = self.provider_config.max_estimated_cost_usd
        if maximum is None:
            return
        if self.price_table is None:
            raise ValueError("a price table is required when a monetary budget is configured")
        if self.provider_config.model not in self.price_table.models:
            raise ValueError("the configured model is missing from the selected price table")

    def readiness(self) -> dict[str, object]:
        price_table_version = self.price_table.version if self.price_table is not None else None
        return {
            "ok": True,
            "executor": "real",
            "provider": self.provider_config.provider.value,
            "model": self.provider_config.model,
            "native_json_schema": self.provider_config.native_json_schema,
            "credentials_configured": bool(self.provider_config.api_key.get_secret_value()),
            "cost_budget_enforced": self.provider_config.max_estimated_cost_usd is not None,
            "price_table_version": price_table_version,
        }

    async def execute(
        self,
        *,
        task_id: str,
        request: ResearchRequest,
        emit: EventEmitter,
        should_cancel: CancellationProbe,
    ) -> JsonObject:
        llm = self.provider_builder(self.provider_config, self.price_table)
        literature = self.literature_builder(self.literature_settings)
        services = RuntimeServices(
            llm=llm,
            search=literature.adapter,
            clock=SystemClock(),
            ids=UUIDIdFactory(),
            store=InMemoryStateStore(),
        )
        graph_budgets = RunBudgets(max_llm_calls=self.provider_config.max_llm_calls_per_task)
        executor = LangGraphTaskExecutor(
            graph=self.graph,
            services=services,
            configurable={
                "network_policy": "allow_search",
                "budgets": graph_budgets,
            },
        )
        try:
            result = await executor.execute(
                task_id=task_id,
                request=request,
                emit=emit,
                should_cancel=should_cancel,
            )
            return self._attach_telemetry(result, llm)
        finally:
            try:
                await self._emit_telemetry(llm, emit)
            finally:
                await literature.aclose()

    @staticmethod
    def _attach_telemetry(result: JsonObject, llm: LLMProvider) -> JsonObject:
        sink = getattr(llm, "telemetry", None)
        if not isinstance(sink, TelemetrySink):
            return result
        enriched = dict(result)
        enriched["provider_telemetry"] = [record.model_dump(mode="json") for record in sink.records]
        return enriched

    @staticmethod
    async def _emit_telemetry(llm: LLMProvider, emit: EventEmitter) -> None:
        sink = getattr(llm, "telemetry", None)
        if not isinstance(sink, TelemetrySink):
            return
        for record in sink.records:
            await emit("llm.invocation", record.model_dump(mode="json"))


def build_real_task_executor(
    provider_config: ProviderRuntimeConfig,
    *,
    literature_settings: LiteratureProviderSettings | None = None,
    price_table: PriceTable | None = None,
) -> RealTaskExecutor:
    return RealTaskExecutor(
        provider_config=provider_config,
        literature_settings=literature_settings or LiteratureProviderSettings(),
        price_table=price_table,
    )


__all__ = [
    "RealTaskExecutor",
    "SystemClock",
    "UUIDIdFactory",
    "build_real_task_executor",
]
