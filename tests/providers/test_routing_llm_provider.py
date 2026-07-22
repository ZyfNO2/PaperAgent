from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TypeVar

import pytest
from pydantic import BaseModel

from paperagent.errors import ProviderError
from paperagent.providers.endpoint import (
    EndpointConfig,
    EndpointHealthState,
    EndpointLimits,
    EndpointProtocol,
    ProviderPool,
    RoutedEndpoint,
)
from paperagent.providers.router import RoutingLLMProvider
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)


class _Reply(BaseModel):
    endpoint: str


class _StubProvider:
    def __init__(self, name: str, outcomes: Sequence[dict[str, str] | ProviderError]) -> None:
        self.name = name
        self._outcomes = list(outcomes)
        self.calls = 0
        self.last_usage = TokenUsage(input_tokens=1, output_tokens=1)
        self.last_latency_ms = 7

    @property
    def model_name(self) -> str:
        return f"model-{self.name}"

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
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, ProviderError):
            raise outcome
        return schema.model_validate(outcome)


class _BlockingProvider(_StubProvider):
    def __init__(self, name: str) -> None:
        super().__init__(name, [{"endpoint": name}])
        self.started = asyncio.Event()
        self.release = asyncio.Event()

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
        self.started.set()
        await self.release.wait()
        return await super().generate_structured(
            task=task,
            scenario=scenario,
            call_index=call_index,
            fixture_version=fixture_version,
            schema=schema,
            messages=messages,
        )


def _failure(provider: str, code: str, *, retryable: bool = True) -> ProviderError:
    return ProviderError(
        f"{provider} failed",
        provider=provider,
        task="test",
        retryable=retryable,
        code=code,
    )


def _endpoint(
    endpoint_id: str,
    provider: _StubProvider,
    *,
    max_concurrency: int = 1,
    failure_threshold: int = 1,
    cooldown_seconds: float = 10.0,
) -> RoutedEndpoint:
    return RoutedEndpoint(
        config=EndpointConfig(
            endpoint_id=endpoint_id,
            vendor="test-vendor",
            protocol=EndpointProtocol.OPENAI_CHAT_COMPLETIONS,
            model=provider.model_name,
            base_url=f"https://{endpoint_id}.example.test/v1",
            limits=EndpointLimits(max_concurrency=max_concurrency),
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        ),
        provider=provider,
    )


def _call(router: RoutingLLMProvider) -> _Reply:
    return asyncio.run(
        router.generate_structured(
            task="router-test",
            scenario="unit",
            call_index=1,
            fixture_version="v1",
            schema=_Reply,
            messages=[Message(role="user", content="return endpoint")],
        )
    )


def test_primary_pool_success_records_winner_identity() -> None:
    primary = _StubProvider("nvidia", [{"endpoint": "nvidia"}])
    fallback = _StubProvider("zen", [{"endpoint": "zen"}])
    router = RoutingLLMProvider(
        [
            ProviderPool("nvidia", (_endpoint("nvidia-a", primary),)),
            ProviderPool("zen", (_endpoint("zen-a", fallback),)),
        ]
    )

    reply = _call(router)

    assert reply.endpoint == "nvidia"
    assert primary.calls == 1
    assert fallback.calls == 0
    assert router.last_pool_id == "nvidia"
    assert router.last_endpoint_id == "nvidia-a"
    assert router.last_attempt_count == 1
    assert router.last_usage == TokenUsage(input_tokens=1, output_tokens=1)


def test_rate_limit_rotates_to_second_account_in_same_pool() -> None:
    account_a = _StubProvider("zen-a", [_failure("zen-a", "LLM_RATE_LIMITED")])
    account_b = _StubProvider("zen-b", [{"endpoint": "zen-b"}])
    router = RoutingLLMProvider(
        [
            ProviderPool(
                "zen",
                (
                    _endpoint("zen-a", account_a),
                    _endpoint("zen-b", account_b),
                ),
            )
        ]
    )

    reply = _call(router)

    assert reply.endpoint == "zen-b"
    assert account_a.calls == 1
    assert account_b.calls == 1
    assert [attempt.endpoint_id for attempt in router.last_attempts] == ["zen-a", "zen-b"]


def test_provider_failure_falls_back_to_next_pool() -> None:
    primary = _StubProvider("nvidia", [_failure("nvidia", "LLM_PROVIDER_5XX")])
    fallback = _StubProvider("zen", [{"endpoint": "zen"}])
    router = RoutingLLMProvider(
        [
            ProviderPool("nvidia", (_endpoint("nvidia-a", primary),)),
            ProviderPool("zen", (_endpoint("zen-a", fallback),)),
        ]
    )

    reply = _call(router)

    assert reply.endpoint == "zen"
    assert router.last_pool_id == "zen"
    assert router.last_endpoint_id == "zen-a"


def test_open_circuit_is_skipped_until_half_open_probe_succeeds() -> None:
    now = [0.0]
    primary = _StubProvider(
        "nvidia",
        [
            _failure("nvidia", "LLM_PROVIDER_5XX"),
            {"endpoint": "nvidia-recovered"},
        ],
    )
    fallback = _StubProvider(
        "zen",
        [
            {"endpoint": "zen-first"},
            {"endpoint": "zen-second"},
        ],
    )
    router = RoutingLLMProvider(
        [
            ProviderPool("nvidia", (_endpoint("nvidia-a", primary),)),
            ProviderPool("zen", (_endpoint("zen-a", fallback),)),
        ],
        clock=lambda: now[0],
    )

    assert _call(router).endpoint == "zen-first"
    now[0] = 1.0
    assert _call(router).endpoint == "zen-second"
    assert primary.calls == 1

    now[0] = 11.0
    assert _call(router).endpoint == "nvidia-recovered"
    snapshots = asyncio.run(router.snapshots())
    primary_snapshot = next(item for item in snapshots if item.endpoint_id == "nvidia-a")
    assert primary_snapshot.state is EndpointHealthState.CLOSED
    assert primary.calls == 2


def test_global_attempt_budget_stops_before_later_pool() -> None:
    primary = _StubProvider("nvidia", [_failure("nvidia", "LLM_PROVIDER_5XX")])
    fallback = _StubProvider("zen", [{"endpoint": "zen"}])
    router = RoutingLLMProvider(
        [
            ProviderPool("nvidia", (_endpoint("nvidia-a", primary),)),
            ProviderPool("zen", (_endpoint("zen-a", fallback),)),
        ],
        max_total_attempts=1,
    )

    with pytest.raises(ProviderError, match="nvidia failed"):
        _call(router)

    assert primary.calls == 1
    assert fallback.calls == 0
    assert router.last_attempt_count == 1


def test_budget_exhaustion_fails_closed_without_fallback() -> None:
    primary = _StubProvider(
        "nvidia",
        [_failure("nvidia", "LLM_BUDGET_EXHAUSTED", retryable=False)],
    )
    fallback = _StubProvider("zen", [{"endpoint": "zen"}])
    router = RoutingLLMProvider(
        [
            ProviderPool("nvidia", (_endpoint("nvidia-a", primary),)),
            ProviderPool("zen", (_endpoint("zen-a", fallback),)),
        ]
    )

    with pytest.raises(ProviderError) as error:
        _call(router)

    assert error.value.code == "LLM_BUDGET_EXHAUSTED"
    assert fallback.calls == 0


def test_least_in_flight_spreads_concurrent_requests() -> None:
    async def scenario() -> None:
        account_a = _BlockingProvider("zen-a")
        account_b = _BlockingProvider("zen-b")
        router = RoutingLLMProvider(
            [
                ProviderPool(
                    "zen",
                    (
                        _endpoint("zen-a", account_a),
                        _endpoint("zen-b", account_b),
                    ),
                )
            ]
        )
        kwargs = {
            "task": "router-test",
            "scenario": "unit",
            "call_index": 1,
            "fixture_version": "v1",
            "schema": _Reply,
            "messages": [Message(role="user", content="return endpoint")],
        }

        first = asyncio.create_task(router.generate_structured(**kwargs))
        await account_a.started.wait()
        second = asyncio.create_task(router.generate_structured(**kwargs))
        await account_b.started.wait()
        account_a.release.set()
        account_b.release.set()
        replies = await asyncio.gather(first, second)

        assert {reply.endpoint for reply in replies} == {"zen-a", "zen-b"}
        assert account_a.calls == 1
        assert account_b.calls == 1

    asyncio.run(scenario())
