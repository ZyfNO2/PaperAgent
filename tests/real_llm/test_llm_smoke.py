"""Real-LLM smoke tests: one structured call per LLM node.

Each test drives ``OpenAILLMProvider.generate_structured`` directly (not through
the LangGraph) with a minimal but schema-plausible user payload and asserts the
returned object satisfies the target Pydantic schema. Skipped unless
``PAPERAGENT_RUN_REAL_LLM=1`` and ``PAPERAGENT_OPENAI_API_KEY`` are set.
"""

from __future__ import annotations

import json
import os

import pytest

from paperagent.prompts import get_prompt
from paperagent.schemas import (
    EvidenceSynthesis,
    FinalReport,
    Message,
    MethodProposal,
    ResearchPlan,
)

# Module-level: carry the ``llm`` marker and skip the whole module when the real
# LLM env gates are not satisfied. Defined inline to avoid fragile conftest
# imports (pytest inserts test dirs onto sys.path, which collides conftest names).
pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        os.getenv("PAPERAGENT_RUN_REAL_LLM") != "1" or not os.getenv("PAPERAGENT_OPENAI_API_KEY"),
        reason="set PAPERAGENT_RUN_REAL_LLM=1 and PAPERAGENT_OPENAI_API_KEY",
    ),
]


def _messages(task: str, user_payload: dict[str, object]) -> list[Message]:
    prompt = get_prompt(task)
    return [
        Message(role="system", content=prompt.system),
        Message(role="user", content=json.dumps(user_payload, ensure_ascii=False, sort_keys=True)),
    ]


@pytest.mark.asyncio
async def test_llm_smoke__planning_schema_valid(real_llm_provider) -> None:
    user_payload = {
        "request": {"question": "How to evaluate citation reliability for a small RAG system?"},
        "budgets": {"max_queries_per_round": 5, "max_retrieval_rounds": 2},
        "available_source_types": ["paper", "web", "user_material"],
    }
    result = await real_llm_provider.generate_structured(
        task="planning",
        scenario="llm_smoke",
        call_index=0,
        fixture_version="v0.1",
        schema=ResearchPlan,
        messages=_messages("planning", user_payload),
    )
    assert isinstance(result, ResearchPlan)
    assert result.status in ("ready", "need_human", "blocked")


@pytest.mark.asyncio
async def test_llm_smoke__evidence_synthesis_schema_valid(real_llm_provider) -> None:
    user_payload = {
        "plan": {
            "problem_statement": "Evaluate citation reliability.",
            "evidence_gap_ids": ["gap-support"],
        },
        "accepted_evidence": [
            {
                "evidence_id": "ev-001",
                "supports_gap_ids": ["gap-support"],
                "summary": "Claim support can be measured.",
            }
        ],
        "coverage_by_gap": {"gap-support": 1},
        "conflicts": [],
    }
    result = await real_llm_provider.generate_structured(
        task="evidence_synthesis",
        scenario="llm_smoke",
        call_index=0,
        fixture_version="v0.1",
        schema=EvidenceSynthesis,
        messages=_messages("evidence_synthesis", user_payload),
    )
    assert isinstance(result, EvidenceSynthesis)
    assert result.feasibility in ("feasible", "partially_feasible", "not_feasible", "unknown")


@pytest.mark.asyncio
async def test_llm_smoke__method_design_schema_valid(real_llm_provider) -> None:
    user_payload = {
        "problem_statement": "Evaluate citation reliability.",
        "verified_findings": [{"claim_id": "c1", "evidence_ids": ["ev-001"]}],
        "constraints": ["single machine"],
        "repair_reason": None,
    }
    result = await real_llm_provider.generate_structured(
        task="method_design",
        scenario="llm_smoke",
        call_index=0,
        fixture_version="v0.1",
        schema=MethodProposal,
        messages=_messages("method_design", user_payload),
    )
    assert isinstance(result, MethodProposal)
    assert result.status == "proposed"


@pytest.mark.asyncio
async def test_llm_smoke__report_schema_valid(real_llm_provider) -> None:
    user_payload = {
        "quality": {"verdict": "pass", "reason_codes": []},
        "accepted_evidence_ids": ["ev-001"],
        "method_status": "proposed",
    }
    result = await real_llm_provider.generate_structured(
        task="report",
        scenario="llm_smoke",
        call_index=0,
        fixture_version="v0.1",
        schema=FinalReport,
        messages=_messages("report", user_payload),
    )
    assert isinstance(result, FinalReport)
    assert result.status in ("completed", "blocked", "partial")
