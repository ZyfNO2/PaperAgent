from __future__ import annotations

from paperagent.providers.base import LLMProvider
from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig


def build_llm_provider(config: ProviderRuntimeConfig) -> LLMProvider:
    if config.provider is LLMProviderName.MISTRAL:
        return MistralLLMProvider(config)
    raise ValueError(f"unsupported LLM provider: {config.provider}")
