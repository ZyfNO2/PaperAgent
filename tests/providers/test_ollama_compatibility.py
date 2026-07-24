from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from paperagent.providers.config import load_provider_config
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig
from paperagent.providers.runtime_factory import build_llm_provider


def test_ollama_loopback_http_is_allowed() -> None:
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OLLAMA,
        model="local-model",
        api_key=SecretStr("ollama-local"),
        base_url="http://127.0.0.1:11434/v1",
    )
    assert config.provider is LLMProviderName.OLLAMA


def test_remote_plain_http_remains_rejected() -> None:
    with pytest.raises(ValidationError):
        ProviderRuntimeConfig(
            provider=LLMProviderName.OPENAI,
            model="remote-model",
            api_key=SecretStr("key"),
            base_url="http://example.com/v1",
        )


def test_ollama_config_uses_local_defaults_without_real_secret() -> None:
    config = load_provider_config(
        environ={
            "PAPERAGENT_LLM_PROVIDER": "ollama",
            "PAPERAGENT_LLM_MODEL": "qwen-local",
        }
    )
    assert config.base_url == "http://127.0.0.1:11434/v1"
    assert config.api_key.get_secret_value() == "ollama-local"


def test_ollama_uses_openai_compatible_adapter() -> None:
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OLLAMA,
        model="local-model",
        api_key=SecretStr("ollama-local"),
        base_url="http://localhost:11434/v1",
    )
    assert isinstance(build_llm_provider(config), OpenAILLMProvider)
