from __future__ import annotations

import os

from paperagent.pricing import PriceTable
from paperagent.providers.base import LLMProvider
from paperagent.providers.hedged import HedgedLLMProvider
from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig, TaskBudget


def _hedging_settings() -> tuple[int, float]:
    maximum = int(os.getenv("PAPERAGENT_LLM_MAX_HEDGED_REQUESTS", "1"))
    delay = float(os.getenv("PAPERAGENT_LLM_HEDGE_DELAY_SECONDS", "0"))
    if not 1 <= maximum <= 4:
        raise ValueError("PAPERAGENT_LLM_MAX_HEDGED_REQUESTS must be between 1 and 4")
    if delay < 0:
        raise ValueError("PAPERAGENT_LLM_HEDGE_DELAY_SECONDS must be non-negative")
    return maximum, delay


def build_llm_provider(
    config: ProviderRuntimeConfig,
    price_table: PriceTable | None = None,
) -> LLMProvider:
    if config.provider is LLMProviderName.MISTRAL:
        return MistralLLMProvider(config, price_table=price_table)
    if config.provider in {
        LLMProviderName.OPENAI,
        LLMProviderName.DEEPSEEK,
        LLMProviderName.OLLAMA,
    }:
        maximum, delay = _hedging_settings()
        budget_config = config.model_copy(
            update={
                "max_llm_calls_per_task": config.max_llm_calls_per_task * maximum,
            }
        )
        budget = TaskBudget(budget_config)

        def build_delegate() -> OpenAILLMProvider:
            return OpenAILLMProvider(
                api_key=config.api_key.get_secret_value(),
                model=config.model,
                base_url=config.base_url,
                timeout_seconds=config.total_timeout_seconds,
                connect_timeout_seconds=config.connect_timeout_seconds,
                read_timeout_seconds=config.read_timeout_seconds,
                max_retries=config.max_attempts - 1,
                max_requests_per_minute=config.max_requests_per_minute,
                max_output_tokens=config.max_output_tokens_per_call,
                native_json_schema=config.native_json_schema,
                allow_schema_repair=config.allow_schema_repair,
                budget=budget,
                price_table=price_table,
            )

        primary = build_delegate()
        if maximum == 1:
            return primary
        delegates = [primary, *(build_delegate() for _ in range(maximum - 1))]
        return HedgedLLMProvider(delegates, hedge_delay_seconds=delay)
    raise ValueError(f"unsupported LLM provider: {config.provider}")
