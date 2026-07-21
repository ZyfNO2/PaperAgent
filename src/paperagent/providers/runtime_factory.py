from __future__ import annotations

from paperagent.pricing import PriceTable
from paperagent.providers.base import LLMProvider
from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig, TaskBudget


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
        return OpenAILLMProvider(
            api_key=config.api_key.get_secret_value(),
            model=config.model,
            base_url=config.base_url,
            timeout_seconds=config.total_timeout_seconds,
            connect_timeout_seconds=config.connect_timeout_seconds,
            read_timeout_seconds=config.read_timeout_seconds,
            max_retries=config.max_attempts - 1,
            max_output_tokens=config.max_output_tokens_per_call,
            native_json_schema=config.native_json_schema,
            budget=TaskBudget(config),
            price_table=price_table,
        )
    raise ValueError(f"unsupported LLM provider: {config.provider}")
