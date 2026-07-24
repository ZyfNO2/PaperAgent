from __future__ import annotations

import pytest

from paperagent.providers.config import load_provider_config
from paperagent.providers.runtime import LLMProviderName


def test_load_provider_config_requires_real_credentials() -> None:
    with pytest.raises(ValueError, match="model"):
        load_provider_config(environ={})
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        load_provider_config(environ={"PAPERAGENT_LLM_MODEL": "model"})


def test_load_provider_config_uses_explicit_values_and_redacts_secret() -> None:
    config = load_provider_config(
        environ={
            "PAPERAGENT_LLM_MODEL": "environment-model",
            "MISTRAL_API_KEY": "secret",
            "PAPERAGENT_LLM_MAX_CALLS": "3",
        },
        model="explicit-model",
    )

    assert config.model == "explicit-model"
    assert config.max_llm_calls_per_task == 3
    assert "secret" not in repr(config)


def test_load_provider_config_supports_openai_compatible_credentials() -> None:
    config = load_provider_config(
        environ={
            "PAPERAGENT_LLM_PROVIDER": "deepseek",
            "PAPERAGENT_LLM_MODEL": "deepseek-v4-flash",
            "PAPERAGENT_OPENAI_API_KEY": "secret",
            "PAPERAGENT_LLM_BASE_URL": "https://opencode.ai/zen/go/v1",
        }
    )

    assert config.provider.value == "deepseek"
    assert config.base_url == "https://opencode.ai/zen/go/v1"
    assert config.api_key.get_secret_value() == "secret"


@pytest.mark.parametrize(
    "effort",
    ["none", "minimal", "low", "medium", "high", "xhigh"],
)
def test_reasoning_effort_values_are_preserved(effort: str) -> None:
    config = load_provider_config(
        environ={
            "PAPERAGENT_LLM_PROVIDER": "openai",
            "PAPERAGENT_LLM_MODEL": "test-model",
            "OPENAI_API_KEY": "test-key",
            "PAPERAGENT_LLM_REASONING_EFFORT": effort,
        }
    )
    assert config.reasoning_effort == effort


def test_provider_specific_defaults_and_boolean_flags() -> None:
    ollama = load_provider_config(
        environ={
            "PAPERAGENT_LLM_PROVIDER": "ollama",
            "PAPERAGENT_LLM_MODEL": "local-model",
            "PAPERAGENT_LLM_ALLOW_SCHEMA_REPAIR": "off",
            "PAPERAGENT_LLM_NATIVE_JSON_SCHEMA": "yes",
        }
    )
    assert ollama.provider is LLMProviderName.OLLAMA
    assert ollama.base_url == "http://127.0.0.1:11434/v1"
    assert ollama.api_key.get_secret_value() == "ollama-local"
    assert ollama.allow_schema_repair is False
    assert ollama.native_json_schema is True

    mistral = load_provider_config(
        environ={
            "PAPERAGENT_LLM_MODEL": "mistral-test",
            "MISTRAL_API_KEY": "mistral-key",
            "PAPERAGENT_LLM_MAX_REQUESTS_PER_MINUTE": "30",
            "PAPERAGENT_LLM_MAX_COST_USD": "0.25",
        }
    )
    assert mistral.provider is LLMProviderName.MISTRAL
    assert mistral.base_url == "https://api.mistral.ai/v1"
    assert mistral.max_requests_per_minute == 30
    assert mistral.max_estimated_cost_usd == 0.25


def test_invalid_environment_values_fail_closed() -> None:
    base = {
        "PAPERAGENT_LLM_PROVIDER": "openai",
        "PAPERAGENT_LLM_MODEL": "test-model",
        "OPENAI_API_KEY": "test-key",
    }
    with pytest.raises(ValueError, match="ALLOW_SCHEMA_REPAIR"):
        load_provider_config(environ={**base, "PAPERAGENT_LLM_ALLOW_SCHEMA_REPAIR": "maybe"})
    with pytest.raises(ValueError, match="REASONING_EFFORT"):
        load_provider_config(environ={**base, "PAPERAGENT_LLM_REASONING_EFFORT": "extreme"})
    with pytest.raises(ValueError, match="model is required"):
        load_provider_config(environ={"OPENAI_API_KEY": "test-key"}, provider="openai")
    with pytest.raises(ValueError, match="API_KEY"):
        load_provider_config(
            environ={"PAPERAGENT_LLM_MODEL": "test-model"},
            provider="openai",
        )
