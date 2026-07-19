from __future__ import annotations

from paperagent.pricing import PriceTable
from paperagent.providers.base import LLMProvider
from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig


def build_llm_provider(
    config: ProviderRuntimeConfig,
    price_table: PriceTable | None = None,
) -> LLMProvider:
    if config.provider is LLMProviderName.MISTRAL:
        return MistralLLMProvider(config, price_table=price_table)
    raise ValueError(f"unsupported LLM provider: {config.provider}")
