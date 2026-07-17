from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from time import monotonic
from typing import cast
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from paperagent.errors import ProviderError as BaseProviderError
from paperagent.telemetry.redaction import redact


class LLMProviderName(StrEnum):
    MISTRAL = "mistral"


class ProviderErrorCode(StrEnum):
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    INVALID_REQUEST = "invalid_request"
    CONNECT = "connect"
    RATE_LIMITED = "rate_limited"
    PROVIDER_5XX = "provider_5xx"
    READ_TIMEOUT = "read_timeout"
    MALFORMED_RESPONSE = "malformed_response"
    SCHEMA_VALIDATION = "schema_validation"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ProviderRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: LLMProviderName = LLMProviderName.MISTRAL
    model: str = Field(min_length=1)
    api_key: SecretStr
    base_url: str = "https://api.mistral.ai/v1"
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    read_timeout_seconds: float = Field(default=60.0, gt=0)
    total_timeout_seconds: float = Field(default=90.0, gt=0)
    max_attempts: int = Field(default=2, ge=1, le=4)
    max_input_tokens_per_task: int = Field(default=32_000, ge=1)
    max_output_tokens_per_call: int = Field(default=4_096, ge=1)
    max_output_tokens_per_task: int = Field(default=16_384, ge=1)
    max_llm_calls_per_task: int = Field(default=12, ge=1)
    task_wall_clock_seconds: float = Field(default=600.0, gt=0)
    max_estimated_cost_usd: float | None = Field(default=None, gt=0)
    allow_schema_repair: bool = True
    native_json_schema: bool = True
    redaction_policy_version: str = "v0.6"
    telemetry_enabled: bool = True

    @model_validator(mode="after")
    def validate_runtime(self) -> ProviderRuntimeConfig:
        if not self.model.strip():
            raise ValueError("model must contain non-whitespace characters")
        if not self.api_key.get_secret_value().strip():
            raise ValueError("api_key must contain non-whitespace characters")
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "base_url must be an HTTPS origin/path without credentials or query data"
            )
        if self.total_timeout_seconds < self.connect_timeout_seconds:
            raise ValueError("total_timeout_seconds must cover connect timeout")
        if self.total_timeout_seconds < self.read_timeout_seconds:
            raise ValueError("total_timeout_seconds must cover read timeout")
        if self.max_output_tokens_per_task < self.max_output_tokens_per_call:
            raise ValueError("task output budget must cover at least one provider call")
        return self


class ProviderError(BaseProviderError):
    def __init__(
        self,
        error_code: ProviderErrorCode,
        message: str,
        *,
        task: str = "llm",
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(
            message,
            provider="mistral",
            task=task,
            retryable=retryable,
            code=f"LLM_{error_code.value.upper()}",
        )
        self.error_code = error_code
        self.status_code = status_code


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class InvocationTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: LLMProviderName
    model: str
    logical_call_id: str
    invocation_id: str
    task: str
    call_index: int
    schema_name: str
    attempt: int = Field(ge=1)
    latency_seconds: float = Field(ge=0)
    usage: UsageRecord = Field(default_factory=UsageRecord)
    outcome: str
    error_code: ProviderErrorCode | None = None
    prompt_fingerprint: str
    response_fingerprint: str | None = None


class TelemetrySink:
    def __init__(self) -> None:
        self._records: list[InvocationTelemetry] = []

    def emit(self, record: InvocationTelemetry) -> None:
        self._records.append(record)

    @property
    def records(self) -> tuple[InvocationTelemetry, ...]:
        return tuple(self._records)


class TaskBudget:
    """Count every physical request or repair attempt against one task budget."""

    def __init__(self, config: ProviderRuntimeConfig) -> None:
        self._config = config
        self._started_at = monotonic()
        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._estimated_cost_usd = 0.0

    @property
    def calls(self) -> int:
        return self._calls

    def reserve_call(self, *, task: str = "llm") -> None:
        self._check_time(task=task)
        if self._calls >= self._config.max_llm_calls_per_task:
            raise ProviderError(
                ProviderErrorCode.BUDGET_EXHAUSTED,
                "maximum LLM calls per task exhausted",
                task=task,
            )
        self._calls += 1

    def record_usage(self, usage: UsageRecord, *, task: str = "llm") -> None:
        if usage.input_tokens is not None:
            self._input_tokens += usage.input_tokens
            if self._input_tokens > self._config.max_input_tokens_per_task:
                raise ProviderError(
                    ProviderErrorCode.BUDGET_EXHAUSTED,
                    "input token budget exhausted",
                    task=task,
                )
        if usage.output_tokens is not None:
            self._output_tokens += usage.output_tokens
            if self._output_tokens > self._config.max_output_tokens_per_task:
                raise ProviderError(
                    ProviderErrorCode.BUDGET_EXHAUSTED,
                    "output token budget exhausted",
                    task=task,
                )
        if usage.estimated_cost_usd is not None:
            self._estimated_cost_usd += usage.estimated_cost_usd
            maximum = self._config.max_estimated_cost_usd
            if maximum is not None and self._estimated_cost_usd > maximum:
                raise ProviderError(
                    ProviderErrorCode.BUDGET_EXHAUSTED,
                    "estimated monetary budget exhausted",
                    task=task,
                )
        self._check_time(task=task)

    def _check_time(self, *, task: str) -> None:
        elapsed = monotonic() - self._started_at
        if elapsed > self._config.task_wall_clock_seconds:
            raise ProviderError(
                ProviderErrorCode.BUDGET_EXHAUSTED,
                "task wall-clock budget exhausted",
                task=task,
            )


def redact_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], redact(value))
