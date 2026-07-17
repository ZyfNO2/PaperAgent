from __future__ import annotations

from pydantic import SecretStr

from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.runtime import ProviderRuntimeConfig
from paperagent.providers.runtime_factory import build_llm_provider


def test_runtime_factory_builds_mistral_provider() -> None:
    provider = build_llm_provider(
        ProviderRuntimeConfig(model="test-model", api_key=SecretStr("secret"))
    )

    assert isinstance(provider, MistralLLMProvider)
