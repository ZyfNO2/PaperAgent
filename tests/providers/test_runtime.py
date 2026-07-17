from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

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
        make_config(connect_timeout_seconds=10, total_timeout_seconds=5)


def test_budget_counts_physical_calls() -> None:
    budget = TaskBudget(make_config(max_llm_calls_per_task=2))
    budget.reserve_call()
    budget.reserve_call()

    with pytest.raises(ProviderError) as exc_info:
        budget.reserve_call()

    assert exc_info.value.code is ProviderErrorCode.BUDGET_EXHAUSTED
    assert budget.calls == 2


def test_budget_fails_closed_on_tokens_and_cost() -> None:
    budget = TaskBudget(
        make_config(
            max_input_tokens=10,
            max_output_tokens=10,
            max_estimated_cost_usd=0.01,
        )
    )

    with pytest.raises(ProviderError) as input_error:
        budget.record_usage(UsageRecord(input_tokens=11))
    assert input_error.value.code is ProviderErrorCode.BUDGET_EXHAUSTED

    cost_budget = TaskBudget(make_config(max_estimated_cost_usd=0.01))
    with pytest.raises(ProviderError) as cost_error:
        cost_budget.record_usage(UsageRecord(estimated_cost_usd=0.02))
    assert cost_error.value.code is ProviderErrorCode.BUDGET_EXHAUSTED


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
