from __future__ import annotations

import json
from typing import Any

from evaluation.schemas import EvaluationCase, ExecutionTrajectory, LLMJudgeResult
from paperagent.providers.base import LLMProvider
from paperagent.schemas import Message

PROMPT_VERSION = "agent-eval-judge.v1"
SYSTEM_PROMPT = """Evaluate relevance, completeness, faithfulness to supplied trajectory evidence,
and instruction following on 1-5 scales. Do not claim real-world factual verification. Return only
the requested structured schema. This is an automated LLM judge, not human review."""


async def run_llm_judge(
    provider: LLMProvider,
    case: EvaluationCase,
    trajectory: ExecutionTrajectory,
) -> LLMJudgeResult:
    evidence: dict[str, Any] = {
        "instruction": case.input,
        "terminal_state": trajectory.terminal_state,
        "steps": [step.model_dump(mode="json") for step in trajectory.steps],
        "final_output": trajectory.final_output,
    }
    return await provider.generate_structured(
        task="agent_evaluation_judge",
        scenario="evaluation",
        call_index=0,
        fixture_version=PROMPT_VERSION,
        schema=LLMJudgeResult,
        messages=[
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=json.dumps(evidence, ensure_ascii=False, default=str)),
        ],
    )
