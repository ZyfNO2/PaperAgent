from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from paperagent.errors import ProviderError
from paperagent.schemas import Message, TokenUsage

SCRIPT = Path(__file__).parents[2] / "scripts" / "test_provider_router_load.py"
SPEC = importlib.util.spec_from_file_location("provider_router_load_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
load = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = load
SPEC.loader.exec_module(load)

T = TypeVar("T", bound=BaseModel)


class SuccessfulDelegate:
    model_name = "fake-success"
    last_usage = TokenUsage(input_tokens=5, output_tokens=2)
    last_latency_ms = 1

    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[T],
        messages: list[Message],
    ) -> T:
        del task, scenario, call_index, fixture_version, messages
        return schema.model_validate({"nonce": "probe-0000", "ok": True})


class FailingDelegate(SuccessfulDelegate):
    model_name = "fake-failure"

    async def generate_structured(self, **kwargs):  # noqa: ANN201, ANN003
        del kwargs
        raise ProviderError(
            "rate limited",
            provider="fake",
            task="load-test",
            retryable=True,
            code="LLM_RATE_LIMITED",
        )


@pytest.mark.asyncio
async def test_instrumented_provider_records_success() -> None:
    provider = load.InstrumentedProvider("endpoint-a", SuccessfulDelegate())
    result = await provider.generate_structured(
        task="load-test",
        scenario="test",
        call_index=0,
        fixture_version="v1",
        schema=load.ProbeResponse,
        messages=[Message(role="user", content="probe")],
    )

    assert result.ok is True
    assert provider.stats.calls == 1
    assert provider.stats.successes == 1
    assert provider.stats.failures == 0
    assert len(provider.stats.latencies_ms) == 1


@pytest.mark.asyncio
async def test_instrumented_provider_records_failure_code() -> None:
    provider = load.InstrumentedProvider("endpoint-b", FailingDelegate())

    with pytest.raises(ProviderError, match="rate limited"):
        await provider.generate_structured(
            task="load-test",
            scenario="test",
            call_index=0,
            fixture_version="v1",
            schema=load.ProbeResponse,
            messages=[Message(role="user", content="probe")],
        )

    assert provider.stats.calls == 1
    assert provider.stats.successes == 0
    assert provider.stats.failures == 1
    assert provider.stats.error_codes == {"LLM_RATE_LIMITED": 1}


def test_percentile_interpolates() -> None:
    assert load._percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0
    assert load._percentile([], 0.95) is None


def test_model_can_be_resolved_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_ROUTER_MODEL", "test/model")
    assert load._resolve_model({"model_env": "TEST_ROUTER_MODEL"}) == "test/model"


def test_missing_api_key_is_rejected_before_live_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_ROUTER_KEY", raising=False)
    raw = {
        "pools": [
            {
                "pool_id": "primary",
                "endpoints": [
                    {
                        "endpoint_id": "endpoint-a",
                        "vendor": "test",
                        "protocol": "openai_chat_completions",
                        "base_url": "https://example.invalid/v1",
                        "api_key_env": "MISSING_ROUTER_KEY",
                        "model": "test/model",
                    }
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="MISSING_ROUTER_KEY"):
        load._build_router(raw)
