from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from paperagent.errors import ProviderError as BaseProviderError
from paperagent.providers.runtime import (
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


def test_provider_error_is_compatible_with_existing_node_error_bridge() -> None:
    error = ProviderError(
        ProviderErrorCode.AUTHENTICATION,
        "authentication failed",
        task="planning",
    )

    assert isinstance(error, BaseProviderError)
    assert error.error_code is ProviderErrorCode.AUTHENTICATION
    assert error.code == "LLM_AUTHENTICATION"
    assert error.provider == "mistral"
    assert error.task == "planning"


def test_budget_counts_physical_calls() -> None:
    budget = TaskBudget(make_config(max_llm_calls_per_task=2))
    budget.reserve_call(task="planning")
    budget.reserve_call(task="planning")

    with pytest.raises(ProviderError) as exc_info:
        budget.reserve_call(task="planning")

    assert exc_info.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED
    assert budget.calls == 2


def test_budget_fails_closed_on_tokens_and_cost() -> None:
    budget = TaskBudget(
        make_config(
            max_input_tokens_per_task=10,
            max_output_tokens_per_call=10,
            max_output_tokens_per_task=10,
            max_estimated_cost_usd=0.01,
        )
    )

    with pytest.raises(ProviderError) as input_error:
        budget.record_usage(UsageRecord(input_tokens=11), task="planning")
    assert input_error.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED

    cost_budget = TaskBudget(make_config(max_estimated_cost_usd=0.01))
    with pytest.raises(ProviderError) as cost_error:
        cost_budget.record_usage(UsageRecord(estimated_cost_usd=0.02), task="planning")
    assert cost_error.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED


def test_monetary_budget_remains_global_across_logical_tasks() -> None:
    budget = TaskBudget(make_config(max_estimated_cost_usd=0.01))

    budget.record_usage(UsageRecord(estimated_cost_usd=0.006), task="planning")
    with pytest.raises(ProviderError, match="estimated monetary budget exhausted"):
        budget.record_usage(UsageRecord(estimated_cost_usd=0.006), task="report")


def test_monetary_budget_fails_closed_when_usage_is_unknown() -> None:
    budget = TaskBudget(make_config(max_estimated_cost_usd=0.01))

    with pytest.raises(ProviderError, match="provider usage is unknown") as exc_info:
        budget.record_usage(UsageRecord(), task="planning")

    assert exc_info.value.error_code is ProviderErrorCode.BUDGET_EXHAUSTED


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


def test_budget_limits_are_isolated_per_logical_task() -> None:
    budget = TaskBudget(
        make_config(
            max_llm_calls_per_task=1,
            max_input_tokens_per_task=10,
            max_output_tokens_per_call=10,
            max_output_tokens_per_task=10,
        )
    )

    budget.reserve_call(task="planning")
    budget.record_usage(UsageRecord(input_tokens=8, output_tokens=8), task="planning")
    budget.reserve_call(task="report")
    budget.record_usage(UsageRecord(input_tokens=8, output_tokens=8), task="report")

    with pytest.raises(ProviderError, match="maximum LLM calls per task exhausted"):
        budget.reserve_call(task="planning:schema-repair")

    assert budget.calls == 2
