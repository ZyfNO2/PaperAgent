from __future__ import annotations

import asyncio
from typing import TypeVar

import pytest
from pydantic import BaseModel, SecretStr

from paperagent.providers.hedged import HedgedLLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig
from paperagent.providers.runtime_factory import build_llm_provider
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)


class _Reply(BaseModel):
    status: str


class _FakeProvider:
    def __init__(
        self,
        *,
        delay: float,
        status: str = "ok",
        error: Exception | None = None,
    ) -> None:
        self.delay = delay
        self.status = status
        self.error = error
        self.started = False
        self.cancelled = False
        self.last_usage = TokenUsage(input_tokens=1, output_tokens=1)
        self.last_latency_ms = int(delay * 1000)

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
        self.started = True
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.error is not None:
            raise self.error
        return schema.model_validate({"status": self.status})


def _call(provider: HedgedLLMProvider) -> _Reply:
    return asyncio.run(
        provider.generate_structured(
            task="hedge-test",
            scenario="unit",
            call_index=1,
            fixture_version="v1",
            schema=_Reply,
            messages=[Message(role="user", content="Return JSON")],
        )
    )


def test_backup_wins_and_cancels_slow_primary() -> None:
    primary = _FakeProvider(delay=0.2, status="primary")
    backup = _FakeProvider(delay=0.01, status="backup")
    provider = HedgedLLMProvider([primary, backup], hedge_delay_seconds=0.01)

    reply = _call(provider)

    assert reply.status == "backup"
    assert primary.started is True
    assert backup.started is True
    assert primary.cancelled is True
    assert provider.last_latency_ms == 10


def test_fast_primary_avoids_starting_backup() -> None:
    primary = _FakeProvider(delay=0, status="primary")
    backup = _FakeProvider(delay=0, status="backup")
    provider = HedgedLLMProvider([primary, backup], hedge_delay_seconds=0.2)

    reply = _call(provider)

    assert reply.status == "primary"
    assert primary.started is True
    assert backup.started is False


def test_primary_failure_starts_backup_without_waiting_for_full_delay() -> None:
    primary = _FakeProvider(delay=0, error=RuntimeError("primary failed"))
    backup = _FakeProvider(delay=0, status="backup")
    provider = HedgedLLMProvider([primary, backup], hedge_delay_seconds=10)

    reply = _call(provider)

    assert reply.status == "backup"
    assert backup.started is True


def test_runtime_factory_enables_bounded_hedging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPERAGENT_LLM_MAX_HEDGED_REQUESTS", "2")
    monkeypatch.setenv("PAPERAGENT_LLM_HEDGE_DELAY_SECONDS", "12")
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OPENAI,
        model="z-ai/glm-5.2",
        api_key=SecretStr("test-key"),
        base_url="https://example.test/v1",
        max_attempts=1,
    )

    provider = build_llm_provider(config)

    assert isinstance(provider, HedgedLLMProvider)
    assert len(provider._delegates) == 2
    assert provider._hedge_delay_seconds == 12


def test_runtime_factory_rejects_unbounded_hedging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPERAGENT_LLM_MAX_HEDGED_REQUESTS", "8")
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OPENAI,
        model="z-ai/glm-5.2",
        api_key=SecretStr("test-key"),
        base_url="https://example.test/v1",
    )

    with pytest.raises(ValueError, match="between 1 and 4"):
        build_llm_provider(config)
