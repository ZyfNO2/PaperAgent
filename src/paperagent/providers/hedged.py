from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel

from paperagent.providers.base import LLMProvider
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)


class HedgedLLMProvider:
    """Race equivalent provider calls and keep the first successful response.

    A primary request starts immediately. If it has not completed after the configured
    delay, one or more backup requests are launched. Once any request returns a valid
    structured response, the remaining tasks are cancelled and awaited for cleanup.

    Cancellation is best-effort: the remote provider may still finish or bill a request
    that already reached its servers. Physical requests remain subject to the shared
    provider rate limiter and shared task budget owned by the delegates.
    """

    def __init__(
        self,
        delegates: Sequence[LLMProvider],
        *,
        hedge_delay_seconds: float,
    ) -> None:
        if not delegates:
            raise ValueError("delegates must not be empty")
        if hedge_delay_seconds < 0:
            raise ValueError("hedge_delay_seconds must be non-negative")
        self._delegates = tuple(delegates)
        self._hedge_delay_seconds = hedge_delay_seconds
        self.last_usage = TokenUsage(input_tokens=0, output_tokens=0)
        self.last_latency_ms = 0

    @property
    def model_name(self) -> str:
        return str(getattr(self._delegates[0], "model_name", "unknown"))

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegates[0], name)

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
        active: dict[asyncio.Task[T], LLMProvider] = {}
        failures: list[Exception] = []

        def launch(delegate: LLMProvider) -> None:
            request = delegate.generate_structured(
                task=task,
                scenario=scenario,
                call_index=call_index,
                fixture_version=fixture_version,
                schema=schema,
                messages=messages,
            )
            active[asyncio.create_task(request)] = delegate

        async def cancel_active() -> None:
            tasks = tuple(active)
            for pending in tasks:
                if not pending.done():
                    pending.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            active.clear()

        def copy_winner_metrics(delegate: LLMProvider) -> None:
            usage = getattr(delegate, "last_usage", None)
            if isinstance(usage, TokenUsage):
                self.last_usage = usage
            latency = getattr(delegate, "last_latency_ms", None)
            if isinstance(latency, int):
                self.last_latency_ms = latency

        async def consume(done: set[asyncio.Task[T]]) -> T | None:
            for completed in done:
                delegate = active.pop(completed)
                try:
                    result = completed.result()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    failures.append(exc)
                    continue
                copy_winner_metrics(delegate)
                await cancel_active()
                return result
            return None

        try:
            launch(self._delegates[0])
            if len(self._delegates) == 1:
                return await next(iter(active))

            if self._hedge_delay_seconds > 0:
                done, _ = await asyncio.wait(
                    tuple(active),
                    timeout=self._hedge_delay_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if done:
                    result = await consume(done)
                    if result is not None:
                        return result

            for delegate in self._delegates[1:]:
                launch(delegate)

            while active:
                done, _ = await asyncio.wait(
                    tuple(active),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                result = await consume(done)
                if result is not None:
                    return result

            if failures:
                raise failures[-1]
            raise RuntimeError("hedged provider call completed without a result")
        finally:
            if active:
                await cancel_active()


__all__ = ["HedgedLLMProvider"]
