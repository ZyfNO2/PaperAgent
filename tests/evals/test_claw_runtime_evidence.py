from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import SecretStr

from paperagent.claw_runtime_evidence import (
    allocate_case_budgets,
    provider_config_for_case,
    summarize_llm_providers,
    summarize_search_budgets,
)
from paperagent.pricing import ModelPrice, PriceTable
from paperagent.providers.runtime import (
    InvocationTelemetry,
    LLMProviderName,
    ProviderRuntimeConfig,
    TelemetrySink,
    UsageRecord,
)


class _Provider:
    def __init__(self, records: tuple[InvocationTelemetry, ...], logical_calls: int) -> None:
        self.telemetry = TelemetrySink()
        for record in records:
            self.telemetry.emit(record)
        self.calls = [object() for _ in range(logical_calls)]


def _config(*, maximum: float | None = 1.0) -> ProviderRuntimeConfig:
    return ProviderRuntimeConfig(
        provider=LLMProviderName.MISTRAL,
        model="mistral-small-latest",
        api_key=SecretStr("test-key"),
        max_estimated_cost_usd=maximum,
    )


def _record(
    *,
    invocation_id: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    outcome: str = "success",
) -> InvocationTelemetry:
    return InvocationTelemetry(
        provider=LLMProviderName.MISTRAL,
        model="mistral-small-latest",
        logical_call_id=f"logical-{invocation_id}",
        invocation_id=invocation_id,
        task="planning",
        call_index=0,
        schema_name="ResearchPlan",
        attempt=1,
        latency_seconds=0.1,
        usage=UsageRecord(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
        ),
        outcome=outcome,
        prompt_fingerprint="prompt",
        response_fingerprint="response",
    )


def test_allocate_case_budgets_is_fair_and_bounded() -> None:
    budgets = allocate_case_budgets(23, 5)

    assert budgets == (5, 5, 5, 4, 4)
    assert sum(budgets) == 23
    assert max(budgets) - min(budgets) == 1


def test_allocate_case_budgets_requires_one_call_per_case() -> None:
    with pytest.raises(ValueError, match="at least one call per case"):
        allocate_case_budgets(3, 4)


def test_provider_config_for_case_splits_full_run_cost_cap() -> None:
    per_case = provider_config_for_case(_config(), selected_case_count=20)

    assert per_case.max_estimated_cost_usd == 0.05
    assert per_case.max_llm_calls_per_task == 12
    assert per_case.max_input_tokens_per_task == 32_000


def test_provider_config_for_case_preserves_unpriced_configuration() -> None:
    config = _config(maximum=None)

    assert provider_config_for_case(config, selected_case_count=20) is config


def test_summarize_search_budgets_accumulates_case_usage() -> None:
    summary = summarize_search_budgets(
        ("case-a", "case-b"),
        (
            {"maximum": 5, "used": 4, "remaining": 1},
            {"maximum": 4, "used": 4, "remaining": 0},
        ),
        configured_total=9,
    )

    assert summary["complete"] is True
    assert summary["used"] == 8
    assert summary["remaining"] == 1
    assert summary["within_configured_total"] is True
    assert summary["cases"][1]["case_id"] == "case-b"


def test_summarize_llm_providers_accumulates_usage_and_cost() -> None:
    price_table = PriceTable(
        version="test-v1",
        models={
            "mistral-small-latest": ModelPrice(
                input_usd_per_million_tokens=Decimal("0.15"),
                output_usd_per_million_tokens=Decimal("0.60"),
            )
        },
    )
    providers = (
        _Provider(
            (_record(invocation_id="1", input_tokens=1_000, output_tokens=500, cost=0.00045),),
            1,
        ),
        _Provider(
            (_record(invocation_id="2", input_tokens=2_000, output_tokens=1_000, cost=0.0009),),
            1,
        ),
    )

    summary = summarize_llm_providers(
        providers,
        config=_config(),
        price_table=price_table,
        selected_case_count=20,
    )

    assert summary["provider_instances"] == 2
    assert summary["logical_calls"] == 2
    assert summary["provider_attempts"] == 2
    assert summary["input_tokens"] == 3_000
    assert summary["output_tokens"] == 1_500
    assert summary["estimated_cost_usd"] == 0.00135
    assert summary["usage_complete"] is True
    assert summary["cost_estimate_complete"] is True
    assert summary["within_configured_cost"] is True
    assert summary["price_table_version"] == "test-v1"
