from __future__ import annotations

from pydantic import SecretStr

from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig
from paperagent.providers.runtime_factory import build_llm_provider


def test_runtime_factory_builds_mistral_provider() -> None:
    provider = build_llm_provider(
        ProviderRuntimeConfig(model="test-model", api_key=SecretStr("secret"))
    )

    assert isinstance(provider, MistralLLMProvider)


def test_runtime_factory_builds_openai_compatible_providers() -> None:
    for provider_name in (LLMProviderName.OPENAI, LLMProviderName.DEEPSEEK):
        provider = build_llm_provider(
            ProviderRuntimeConfig(
                provider=provider_name,
                model="deepseek-v4-flash",
                api_key=SecretStr("secret"),
                base_url="https://opencode.ai/zen/go/v1",
            )
        )

        assert isinstance(provider, OpenAILLMProvider)
        assert provider.model_name == "deepseek-v4-flash"
