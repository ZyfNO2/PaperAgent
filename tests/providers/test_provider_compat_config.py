from __future__ import annotations

import pytest

from paperagent.providers.config import load_provider_config


def _base_env() -> dict[str, str]:
    return {
        "PAPERAGENT_LLM_PROVIDER": "openai",
        "PAPERAGENT_LLM_MODEL": "vendor/model",
        "PAPERAGENT_OPENAI_API_KEY": "test-key",
    }


def test_schema_repair_defaults_on_for_openai_compatible_models() -> None:
    config = load_provider_config(environ=_base_env())
    assert config.allow_schema_repair is True


def test_schema_repair_can_be_disabled_per_deployment() -> None:
    env = _base_env()
    env["PAPERAGENT_LLM_ALLOW_SCHEMA_REPAIR"] = "off"
    config = load_provider_config(environ=env)
    assert config.allow_schema_repair is False


def test_schema_repair_rejects_ambiguous_boolean_values() -> None:
    env = _base_env()
    env["PAPERAGENT_LLM_ALLOW_SCHEMA_REPAIR"] = "sometimes"
    with pytest.raises(ValueError, match="PAPERAGENT_LLM_ALLOW_SCHEMA_REPAIR"):
        load_provider_config(environ=env)
