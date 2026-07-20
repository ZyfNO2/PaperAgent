from __future__ import annotations

import os

import pytest
from pydantic import BaseModel, SecretStr

from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.runtime import ProviderRuntimeConfig
from paperagent.schemas import (
    EvidenceSynthesis,
    FinalReport,
    Message,
    MethodProposal,
    ResearchPlan,
)

PRODUCTION_SCHEMA_CASES: tuple[tuple[str, type[BaseModel], str], ...] = (
    (
        "planning",
        ResearchPlan,
        "Return a minimal blocked research plan. Set status to blocked, provide a non-empty "
        "block_reason, set clarification_question to null, and keep all list fields empty.",
    ),
    (
        "synthesis",
        EvidenceSynthesis,
        "Return a minimal evidence synthesis for a case with no accepted evidence. Use empty "
        "assessment, finding, conflict, and limitation lists, and set feasibility to unknown.",
    ),
    (
        "method",
        MethodProposal,
        "Return a minimal proposed method object with one baseline, one module, no integration "
        "contracts, one key experiment, one ablation, one risk, one stop condition, and no "
        "evidence identifiers. The legacy modules[0].module_id must exactly equal "
        "methodology_plan.modules[0].name. Keep evidence_ids and methodology_plan.evidence "
        "empty. The legacy stop_conditions list must exactly equal "
        "methodology_plan.stop_conditions.",
    ),
    (
        "report",
        FinalReport,
        "Return a minimal partial final report with an executive summary, empty finding lists, "
        "null proposed_method and experiment_plan, one limitation, one next action, and no "
        "evidence identifiers.",
    ),
)


@pytest.mark.real_provider
@pytest.mark.network
@pytest.mark.asyncio
@pytest.mark.parametrize(("task", "schema", "instruction"), PRODUCTION_SCHEMA_CASES)
async def test_live_mistral_production_schema(
    task: str,
    schema: type[BaseModel],
    instruction: str,
) -> None:
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
            max_attempts=2,
            max_llm_calls_per_task=2,
            max_input_tokens_per_task=8_000,
            max_output_tokens_per_call=2_048,
            max_output_tokens_per_task=4_096,
            task_wall_clock_seconds=120,
        )
    )
    result = await provider.generate_structured(
        task=task,
        scenario="live",
        call_index=0,
        fixture_version="v0.1",
        schema=schema,
        messages=[Message(role="user", content=instruction)],
    )

    assert isinstance(result, schema)
