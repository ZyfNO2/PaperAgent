from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from paperagent.errors import FixtureNotFoundError, ProviderError
from paperagent.providers.base import FixtureKey
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMCall:
    key: FixtureKey
    message_count: int
    schema_name: str


class FakeLLMProvider:
    provider_name = "fake_llm"
    model_name = "fake-structured-v0.1"

    def __init__(
        self,
        *,
        fixtures: dict[FixtureKey | tuple[str, str, int, str], str],
        failures: dict[FixtureKey | tuple[str, str, int, str], Exception] | None = None,
    ) -> None:
        self._fixtures = {self._normalize_key(key): value for key, value in fixtures.items()}
        self._failures = {
            self._normalize_key(key): value for key, value in (failures or {}).items()
        }
        self.calls: list[LLMCall] = []
        self.last_usage = TokenUsage(input_tokens=10, output_tokens=20)
        self.last_latency_ms = 5

    @staticmethod
    def _normalize_key(key: FixtureKey | tuple[str, str, int, str]) -> FixtureKey:
        if isinstance(key, FixtureKey):
            return key
        return FixtureKey(task=key[0], scenario=key[1], call_index=key[2], fixture_version=key[3])

    def raw_fixture(self, key: FixtureKey) -> str:
        try:
            return self._fixtures[key]
        except KeyError as exc:
            raise FixtureNotFoundError(key.as_path()) from exc

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
        key = FixtureKey(
            task=task,
            scenario=scenario,
            call_index=call_index,
            fixture_version=fixture_version,
        )
        self.calls.append(
            LLMCall(key=key, message_count=len(messages), schema_name=schema.__name__)
        )
        if key in self._failures:
            raise self._failures[key]
        raw = self.raw_fixture(key)
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "fixture JSON is invalid",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_JSON_INVALID",
            ) from exc
        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(
                "fixture failed schema validation",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_SCHEMA_INVALID",
            ) from exc
