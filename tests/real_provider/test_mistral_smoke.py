from __future__ import annotations

import os

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.runtime import ProviderRuntimeConfig
from paperagent.schemas import Message


class SmokeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


@pytest.mark.real_provider
@pytest.mark.network
@pytest.mark.asyncio
async def test_live_mistral_structured_output() -> None:
    if os.environ.get("PAPERAGENT_RUN_REAL_LLM") != "1":
        pytest.skip("set PAPERAGENT_RUN_REAL_LLM=1 to enable live Mistral smoke")
    api_key = os.environ.get("MISTRAL_API_KEY")
    model = os.environ.get("PAPERAGENT_MISTRAL_MODEL")
    if not api_key or not model:
        pytest.skip("MISTRAL_API_KEY and PAPERAGENT_MISTRAL_MODEL are required")

    provider = MistralLLMProvider(
        ProviderRuntimeConfig(
            model=model,
            api_key=SecretStr(api_key),
            max_attempts=1,
            max_llm_calls_per_task=1,
            max_input_tokens=1_000,
            max_output_tokens=128,
            task_wall_clock_seconds=60,
        )
    )
    result = await provider.generate_structured(
        task="v0.6-live-smoke",
        scenario="live",
        call_index=0,
        fixture_version="v0.1",
        schema=SmokeOutput,
        messages=[Message(role="user", content='Return JSON with status equal to "ok".')],
    )

    assert result.status == "ok"
