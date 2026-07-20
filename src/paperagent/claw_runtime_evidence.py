from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from paperagent.pricing import PriceTable
from paperagent.providers.runtime import (
    InvocationTelemetry,
    ProviderRuntimeConfig,
    TelemetrySink,
)


def allocate_case_budgets(total: int, case_count: int) -> tuple[int, ...]:
    """Split one hard full-run budget fairly without exceeding it."""

    if total < 1:
        raise ValueError("total budget must be positive")
    if case_count < 1:
        raise ValueError("case_count must be positive")
    if total < case_count:
        raise ValueError("total budget must allow at least one call per case")
    base, remainder = divmod(total, case_count)
    return tuple(base + (index < remainder) for index in range(case_count))


def provider_config_for_case(
    config: ProviderRuntimeConfig,
    *,
    selected_case_count: int,
    max_logical_calls: int | None = None,
) -> ProviderRuntimeConfig:
    """Create isolated per-case physical-request and monetary budgets.

    Graph execution counts logical LLM calls, while a provider budget counts every physical
    request, including schema-repair attempts. The physical limit therefore reserves the configured
    number of attempts for every allowed logical call. A configured monetary ceiling is interpreted
    as the full-run ceiling and divided evenly across cases, providing a conservative aggregate cap.
    """

    if selected_case_count < 1:
        raise ValueError("selected_case_count must be positive")
    if max_logical_calls is not None and max_logical_calls < 1:
        raise ValueError("max_logical_calls must be positive")
    updates: dict[str, int | float] = {}
    maximum = config.max_estimated_cost_usd
    if maximum is not None:
        updates["max_estimated_cost_usd"] = maximum / selected_case_count
    if max_logical_calls is not None:
        updates["max_llm_calls_per_task"] = max_logical_calls * config.max_attempts
    return config.model_copy(update=updates) if updates else config


def summarize_search_budgets(
    case_ids: Iterable[str],
    budgets: Iterable[dict[str, int | None] | None],
    *,
    configured_total: int,
) -> dict[str, Any]:
    case_rows: list[dict[str, str | int | None]] = []
    total_used = 0
    total_remaining = 0
    complete = True
    for case_id, budget in zip(case_ids, budgets, strict=True):
        if budget is None:
            complete = False
            case_rows.append(
                {
                    "case_id": case_id,
                    "maximum": None,
                    "used": None,
                    "remaining": None,
                }
            )
            continue
        maximum = budget.get("maximum")
        used = budget.get("used")
        remaining = budget.get("remaining")
        if not (isinstance(maximum, int) and isinstance(used, int) and isinstance(remaining, int)):
            complete = False
        else:
            total_used += used
            total_remaining += remaining
        case_rows.append(
            {
                "case_id": case_id,
                "maximum": maximum,
                "used": used,
                "remaining": remaining,
            }
        )
    return {
        "configured_total": configured_total,
        "used": total_used if complete else None,
        "remaining": total_remaining if complete else None,
        "complete": complete,
        "within_configured_total": total_used <= configured_total if complete else None,
        "cases": case_rows,
    }


def _telemetry_records(provider: object) -> tuple[InvocationTelemetry, ...]:
    telemetry = getattr(provider, "telemetry", None)
    if isinstance(telemetry, TelemetrySink):
        return telemetry.records
    return ()


def _logical_call_count(provider: object) -> int:
    calls = getattr(provider, "calls", None)
    if isinstance(calls, list):
        return len(calls)
    if isinstance(calls, tuple):
        return len(calls)
    return 0


def summarize_llm_providers(
    providers: Iterable[object],
    *,
    config: ProviderRuntimeConfig,
    price_table: PriceTable | None,
    selected_case_count: int,
) -> dict[str, Any]:
    provider_list = tuple(providers)
    records = tuple(record for provider in provider_list for record in _telemetry_records(provider))
    logical_calls = sum(_logical_call_count(provider) for provider in provider_list)
    input_tokens = sum(record.usage.input_tokens or 0 for record in records)
    output_tokens = sum(record.usage.output_tokens or 0 for record in records)
    estimated_costs = [
        record.usage.estimated_cost_usd
        for record in records
        if record.usage.estimated_cost_usd is not None
    ]
    usage_complete = bool(records) and all(
        record.usage.input_tokens is not None and record.usage.output_tokens is not None
        for record in records
    )
    cost_estimate_complete = (
        bool(records)
        and price_table is not None
        and all(record.usage.estimated_cost_usd is not None for record in records)
    )
    estimated_cost_usd = round(sum(estimated_costs), 8) if estimated_costs else None
    maximum = config.max_estimated_cost_usd
    within_configured_cost: bool | None = None
    if maximum is not None and estimated_cost_usd is not None and cost_estimate_complete:
        within_configured_cost = estimated_cost_usd <= maximum
    per_case_maximum = maximum / selected_case_count if maximum is not None else None

    return {
        "provider": config.provider.value,
        "model": config.model,
        "provider_instances": len(provider_list),
        "logical_calls": logical_calls,
        "provider_attempts": len(records),
        "successful_attempts": sum(record.outcome == "success" for record in records),
        "failed_attempts": sum(record.outcome != "success" for record in records),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usage_complete": usage_complete,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_estimate_complete": cost_estimate_complete,
        "configured_full_run_max_cost_usd": maximum,
        "configured_per_case_max_cost_usd": per_case_maximum,
        "within_configured_cost": within_configured_cost,
        "price_table_loaded": price_table is not None,
        "price_table_version": price_table.version if price_table is not None else None,
    }


__all__ = [
    "allocate_case_budgets",
    "provider_config_for_case",
    "summarize_llm_providers",
    "summarize_search_budgets",
]
