from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

import paperagent.providers.runtime as runtime_module
from paperagent.claw_runtime_evidence import provider_config_for_case
from paperagent.errors import ProviderError as BaseProviderError
from paperagent.providers.runtime import (
    LLMProviderName,
    ProviderError,
    ProviderErrorCode,
    ProviderRuntimeConfig,
    TaskBudget,
    UsageRecord,
    redact_mapping,
)


def make_config(**overrides: object) -> ProviderRuntimeConfig:
    values: dict[str, object] = {
        "model": "test-model",
        "api_key": SecretStr("secret-value"),
    }
    values.update(overrides)
    return ProviderRuntimeConfig.model_validate(values)


def test_runtime_config_requires_https_and_consistent_timeouts() -> None:
    with pytest.raises(ValidationError):
        make_config(base_url="http://example.test")
    with pytest.raises(ValidationError):
        make_config(base_url="https://user:password@example.test/v1")
    with pytest.raises(ValidationError):
        make_config(connect_timeout_seconds=10, total_timeout_seconds=5)
    with pytest.raises(ValidationError):
        make_config(max_output_tokens_per_call=20, max_output_tokens_per_task=10)


def test_provider_error_preserves_actual_provider() -> None:
    error = ProviderError(
        ProviderErrorCode.AUTHENTICATION,
        "authentication failed",
        provider="openai",
        task="planning",
    )

    assert isinstance(error, BaseProviderError)
    assert error.error_code is ProviderErrorCode.AUTHENTICATION
    assert error.code == "LLM_AUTHENTICATION"
    assert error.provider == "openai"
    assert error.task == "planning"


def test_production_budget_enforces_call_ceiling() -> None:
    budget = TaskBudget(make_config(max_llm_calls_per_task=2))
    budget.reserve_call(task="planning")
    budget.reserve_call(task="planning")

    with pytest.raises(ProviderError) as caught:
        budget.reserve_call(task="planning")

    assert caught.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED
    assert budget.calls == 2


def test_production_budget_enforces_tokens_and_unknown_cost() -> None:
    token_budget = TaskBudget(
        make_config(
            max_input_tokens_per_task=10,
            max_output_tokens_per_call=10,
            max_output_tokens_per_task=10,
        )
    )
    with pytest.raises(ProviderError) as token_error:
        token_budget.record_usage(
            UsageRecord(input_tokens=11, output_tokens=1, estimated_cost_usd=0.0),
            task="planning",
        )
    assert token_error.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED

    cost_budget = TaskBudget(make_config(max_estimated_cost_usd=0.01))
    with pytest.raises(ProviderError) as cost_error:
        cost_budget.record_usage(
            UsageRecord(input_tokens=1, output_tokens=1, estimated_cost_usd=None),
            task="planning",
        )
    assert cost_error.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED


def test_benchmark_case_config_disables_non_time_budget_limits() -> None:
    config = make_config(
        max_llm_calls_per_task=1,
        max_input_tokens_per_task=1,
        max_output_tokens_per_call=1,
        max_output_tokens_per_task=1,
        max_estimated_cost_usd=0.01,
    )
    benchmark_config = provider_config_for_case(
        config,
        selected_case_count=10,
        max_logical_calls=2,
    )

    assert benchmark_config.enforce_task_budget_limits is False
    assert benchmark_config.max_llm_calls_per_task == 2 * config.max_attempts

    budget = TaskBudget(benchmark_config)
    for _ in range(5):
        budget.reserve_call(task="planning")
    budget.record_usage(
        UsageRecord(input_tokens=100, output_tokens=100, estimated_cost_usd=None),
        task="planning",
    )
    assert budget.calls == 5


def test_wall_clock_timeout_remains_enforced_when_budget_limits_are_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter((0.0, 2.0))
    monkeypatch.setattr(runtime_module, "monotonic", lambda: next(times))
    budget = TaskBudget(
        make_config(
            provider=LLMProviderName.OPENAI,
            task_wall_clock_seconds=1.0,
            enforce_task_budget_limits=False,
        )
    )

    with pytest.raises(ProviderError) as caught:
        budget.reserve_call(task="planning")

    assert caught.value.error_code is ProviderErrorCode.READ_TIMEOUT
    assert caught.value.provider == "openai"
    assert caught.value.retryable is True


def test_redaction_recurses_without_mutating_safe_values() -> None:
    payload = {
        "Authorization": "Bearer secret",
        "nested": {"api_key": "secret", "model": "safe"},
        "items": [{"token": "secret"}, {"value": 3}],
    }

    assert redact_mapping(payload) == {
        "Authorization": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]", "model": "safe"},
        "items": [{"token": "[REDACTED]"}, {"value": 3}],
    }
