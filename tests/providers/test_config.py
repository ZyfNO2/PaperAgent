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
