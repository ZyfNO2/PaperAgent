from __future__ import annotations

import pytest

from paperagent.providers.config import load_provider_config


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
