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


def test_budget_counts_physical_calls_without_enforcing_a_call_ceiling() -> None:
    budget = TaskBudget(make_config(max_llm_calls_per_task=2))
    budget.reserve_call(task="planning")
    budget.reserve_call(task="planning")
    budget.reserve_call(task="planning")
    assert budget.calls == 3


def test_budget_records_tokens_and_cost_without_enforcing_ceilings() -> None:
    budget = TaskBudget(
        make_config(
            max_input_tokens_per_task=10,
            max_output_tokens_per_call=10,
            max_output_tokens_per_task=10,
            max_estimated_cost_usd=0.01,
        )
    )

    budget.record_usage(
        UsageRecord(input_tokens=11, output_tokens=11, estimated_cost_usd=0.02),
        task="planning",
    )


def test_unknown_cost_does_not_exhaust_otherwise_valid_budget() -> None:
    budget = TaskBudget(make_config(max_estimated_cost_usd=0.01))

    budget.record_usage(
        UsageRecord(input_tokens=10, output_tokens=5, estimated_cost_usd=None),
        task="planning",
    )


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
