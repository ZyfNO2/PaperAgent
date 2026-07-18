from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import SecretStr

from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig


def load_provider_config(
    *,
    environ: Mapping[str, str] | None = None,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> ProviderRuntimeConfig:
    values = os.environ if environ is None else environ
    resolved_provider = provider or values.get("PAPERAGENT_LLM_PROVIDER") or "mistral"
    resolved_model = model or values.get("PAPERAGENT_LLM_MODEL")
    provider_name = LLMProviderName(resolved_provider)
    if provider_name is LLMProviderName.MISTRAL:
        default_base_url = "https://api.mistral.ai/v1"
    elif provider_name is LLMProviderName.OLLAMA:
        default_base_url = "http://127.0.0.1:11434/v1"
    else:
        default_base_url = "https://api.openai.com/v1"
    resolved_base_url = base_url or values.get("PAPERAGENT_LLM_BASE_URL") or default_base_url
    if provider_name is LLMProviderName.MISTRAL:
        api_key = values.get("MISTRAL_API_KEY")
        credential_name = "MISTRAL_API_KEY"
    elif provider_name is LLMProviderName.OLLAMA:
        api_key = (
            values.get("PAPERAGENT_OPENAI_API_KEY")
            or values.get("OPENAI_API_KEY")
            or "ollama-local"
        )
        credential_name = "optional local Ollama API key"
    else:
        api_key = values.get("PAPERAGENT_OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
        credential_name = "PAPERAGENT_OPENAI_API_KEY or OPENAI_API_KEY"
    if not resolved_model:
        raise ValueError("PAPERAGENT_LLM_MODEL or an explicit model is required")
    if not api_key:
        raise ValueError(f"{credential_name} is required for the real executor")

    return ProviderRuntimeConfig(
        provider=provider_name,
        model=resolved_model,
        api_key=SecretStr(api_key),
        base_url=resolved_base_url,
        connect_timeout_seconds=float(values.get("PAPERAGENT_LLM_CONNECT_TIMEOUT", "5")),
        read_timeout_seconds=float(values.get("PAPERAGENT_LLM_READ_TIMEOUT", "60")),
        total_timeout_seconds=float(values.get("PAPERAGENT_LLM_TOTAL_TIMEOUT", "90")),
        max_attempts=int(values.get("PAPERAGENT_LLM_MAX_ATTEMPTS", "2")),
        max_input_tokens_per_task=int(
            values.get("PAPERAGENT_LLM_MAX_INPUT_TOKENS_PER_TASK", "32000")
        ),
        max_output_tokens_per_call=int(
            values.get("PAPERAGENT_LLM_MAX_OUTPUT_TOKENS_PER_CALL", "4096")
        ),
        max_output_tokens_per_task=int(
            values.get("PAPERAGENT_LLM_MAX_OUTPUT_TOKENS_PER_TASK", "16384")
        ),
        max_llm_calls_per_task=int(values.get("PAPERAGENT_LLM_MAX_CALLS", "12")),
        task_wall_clock_seconds=float(values.get("PAPERAGENT_LLM_TASK_TIMEOUT", "600")),
        max_estimated_cost_usd=(
            float(values["PAPERAGENT_LLM_MAX_COST_USD"])
            if values.get("PAPERAGENT_LLM_MAX_COST_USD")
            else None
        ),
    )
