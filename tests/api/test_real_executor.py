from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from paperagent.api import create_app
from paperagent.api.real_executor import RealTaskExecutor
from paperagent.pricing import ModelPrice, PriceTable
from paperagent.providers.runtime import (
    InvocationTelemetry,
    LLMProviderName,
    ProviderRuntimeConfig,
    TelemetrySink,
)
from paperagent.schemas import ExecutionMeta, FinalReport, ResearchRequest


class FakeLLM:
    model_name = "fake-real-model"

    def __init__(self) -> None:
        self.telemetry = TelemetrySink()
        self.telemetry.emit(
            InvocationTelemetry(
                provider=LLMProviderName.MISTRAL,
                model="fake-real-model",
                logical_call_id="logical-1",
                invocation_id="invocation-1",
                task="planning",
                call_index=0,
                schema_name="ResearchPlan",
                attempt=1,
                latency_seconds=0.01,
                outcome="success",
                prompt_fingerprint="a" * 64,
                response_fingerprint="b" * 64,
            )
        )

    async def generate_structured(self, **_: Any) -> Any:
        raise AssertionError("fake graph must not call the LLM")


class FakeGraph:
    def astream(self, *_: Any, **__: Any) -> AsyncIterator[dict[str, Any]]:
        async def generate() -> AsyncIterator[dict[str, Any]]:
            yield {
                "execution": ExecutionMeta(status="completed"),
                "report": FinalReport(
                    status="completed",
                    executive_summary="completed",
                    verified_findings=[],
                    inferred_findings=[],
                    limitations=["synthetic executor test"],
                ),
                "trace": [],
            }

        return generate()


class FakeLiteratureRuntime:
    adapter = object()

    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def price_table() -> PriceTable:
    return PriceTable(
        version="test",
        models={
            "fake-real-model": ModelPrice(
                input_usd_per_million_tokens=Decimal("1"),
                output_usd_per_million_tokens=Decimal("2"),
            )
        },
    )


@pytest.mark.asyncio
async def test_real_executor_creates_per_task_services_and_preserves_telemetry() -> None:
    runtimes: list[FakeLiteratureRuntime] = []

    def build_literature(_: Any) -> FakeLiteratureRuntime:
        runtime = FakeLiteratureRuntime()
        runtimes.append(runtime)
        return runtime

    emitted: list[tuple[str, dict[str, Any]]] = []

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        emitted.append((event_type, payload))

    executor = RealTaskExecutor(
        provider_config=ProviderRuntimeConfig(
            model="fake-real-model",
            api_key=SecretStr("secret"),
        ),
        graph=FakeGraph(),
        provider_builder=lambda _config, _prices: FakeLLM(),
        literature_builder=build_literature,
    )
    result = await executor.execute(
        task_id="task-1",
        request=ResearchRequest(question="test real executor"),
        emit=emit,
        should_cancel=lambda: False,
    )

    assert result["execution"]["status"] == "completed"
    assert result["provider_telemetry"][0]["invocation_id"] == "invocation-1"
    assert emitted[-1][0] == "llm.invocation"
    assert runtimes[0].closed is True


def test_real_executor_requires_pricing_for_a_monetary_budget() -> None:
    config = ProviderRuntimeConfig(
        model="fake-real-model",
        api_key=SecretStr("secret"),
        max_estimated_cost_usd=0.1,
    )

    with pytest.raises(ValueError, match="price table"):
        RealTaskExecutor(provider_config=config)
    with pytest.raises(ValueError, match="missing"):
        RealTaskExecutor(
            provider_config=config,
            price_table=PriceTable(
                version="test",
                models={
                    "another-model": ModelPrice(
                        input_usd_per_million_tokens=Decimal("1"),
                        output_usd_per_million_tokens=Decimal("1"),
                    )
                },
            ),
        )


def test_real_executor_readiness_never_exposes_secret(tmp_path: Path) -> None:
    executor = RealTaskExecutor(
        provider_config=ProviderRuntimeConfig(
            model="fake-real-model",
            api_key=SecretStr("top-secret"),
            max_estimated_cost_usd=0.1,
        ),
        price_table=price_table(),
    )
    app = create_app(executor=executor, database_path=tmp_path / "real-ready.db")

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["executor"]["executor"] == "real"
    assert payload["checks"]["executor"]["credentials_configured"] is True
    assert payload["checks"]["executor"]["cost_budget_enforced"] is True
    assert payload["checks"]["executor"]["price_table_version"] == "test"
    assert "top-secret" not in response.text
