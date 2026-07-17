from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from paperagent.api import create_app
from paperagent.api.real_executor import RealTaskExecutor
from paperagent.providers.runtime import (
    InvocationTelemetry,
    LLMProviderName,
    ProviderRuntimeConfig,
    TelemetrySink,
)
from paperagent.schemas import ExecutionMeta, ResearchRequest


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
            yield {"execution": ExecutionMeta(status="completed"), "trace": []}

        return generate()


class FakeLiteratureRuntime:
    adapter = object()

    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


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
        provider_builder=lambda _: FakeLLM(),
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


def test_real_executor_readiness_never_exposes_secret(tmp_path: Any) -> None:
    executor = RealTaskExecutor(
        provider_config=ProviderRuntimeConfig(
            model="fake-real-model",
            api_key=SecretStr("top-secret"),
        )
    )
    app = create_app(executor=executor, database_path=tmp_path / "real-ready.db")

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["executor"]["executor"] == "real"
    assert payload["checks"]["executor"]["credentials_configured"] is True
    assert "top-secret" not in response.text
