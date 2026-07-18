"""Real LLM smoke harness.

Runs one real Chat Completions call against each of the four structured LLM nodes
(planning, evidence_synthesis, method_design, report) and reports a per-node
status. Mirrors the shape of :mod:`paperagent.provider_smoke` but targets the
LLM provider instead of the literature providers.

The harness never imports network code at module import time; it only reaches the
network when :func:`run_llm_smoke` is awaited with a configured provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from paperagent.errors import ProviderError, ProviderTimeoutError
from paperagent.nodes._shared import json_message
from paperagent.prompts import get_prompt
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.schemas import (
    EvidenceSynthesis,
    FinalReport,
    Message,
    MethodProposal,
    ResearchPlan,
)

_DEFAULT_QUESTION = "How to evaluate citation reliability for a small RAG system?"

# Per-node status vocabulary.
_STATUS_SUCCESS = "success"
_STATUS_SCHEMA_INVALID = "schema_invalid"
_STATUS_PROVIDER_ERROR = "provider_error"
_STATUS_TIMEOUT = "timeout"


@dataclass(frozen=True)
class LLMSmokeSummary:
    """Aggregate result of the four-node real LLM smoke run."""

    planning: str
    evidence_synthesis: str
    method_design: str
    report: str

    @property
    def passed(self) -> bool:
        return all(
            status == _STATUS_SUCCESS
            for status in (self.planning, self.evidence_synthesis, self.method_design, self.report)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "nodes": {
                "planning": self.planning,
                "evidence_synthesis": self.evidence_synthesis,
                "method_design": self.method_design,
                "report": self.report,
            },
        }


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, ProviderTimeoutError):
        return _STATUS_TIMEOUT
    if isinstance(exc, ProviderError):
        if exc.code == "LLM_RESPONSE_SCHEMA_INVALID":
            return _STATUS_SCHEMA_INVALID
        return _STATUS_PROVIDER_ERROR
    return _STATUS_PROVIDER_ERROR


def _planning_payload(question: str) -> Mapping[str, Any]:
    return {
        "request": {"question": question},
        "budgets": {"max_queries_per_round": 5, "max_retrieval_rounds": 2},
        "available_source_types": ["paper", "web", "user_material"],
    }


def _evidence_synthesis_payload() -> Mapping[str, Any]:
    return {
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


def _method_design_payload() -> Mapping[str, Any]:
    return {
        "problem_statement": "Evaluate citation reliability.",
        "verified_findings": [{"claim_id": "c1", "evidence_ids": ["ev-001"]}],
        "constraints": ["single machine"],
        "repair_reason": None,
    }


def _report_payload() -> Mapping[str, Any]:
    return {
        "quality": {"verdict": "pass", "reason_codes": []},
        "accepted_evidence_ids": ["ev-001"],
        "method_status": "proposed",
    }


async def _run_node(
    provider: OpenAILLMProvider,
    *,
    task: str,
    schema: type[Any],
    user_payload: Mapping[str, Any],
) -> str:
    prompt = get_prompt(task)
    messages = [
        Message(role="system", content=prompt.system),
        Message(role="user", content=json_message(user_payload)),
    ]
    try:
        await provider.generate_structured(
            task=task,
            scenario="llm_smoke",
            call_index=0,
            fixture_version="v0.1",
            schema=schema,
            messages=messages,
        )
        return _STATUS_SUCCESS
    except Exception as exc:
        return _classify_exception(exc)


async def run_llm_smoke(
    provider: OpenAILLMProvider,
    *,
    question: str | None = None,
) -> LLMSmokeSummary:
    """Run one real LLM call per structured node and return per-node status."""
    selected_question = question or _DEFAULT_QUESTION

    planning = await _run_node(
        provider,
        task="planning",
        schema=ResearchPlan,
        user_payload=_planning_payload(selected_question),
    )
    evidence_synthesis = await _run_node(
        provider,
        task="evidence_synthesis",
        schema=EvidenceSynthesis,
        user_payload=_evidence_synthesis_payload(),
    )
    method_design = await _run_node(
        provider,
        task="method_design",
        schema=MethodProposal,
        user_payload=_method_design_payload(),
    )
    report = await _run_node(
        provider,
        task="report",
        schema=FinalReport,
        user_payload=_report_payload(),
    )
    return LLMSmokeSummary(
        planning=planning,
        evidence_synthesis=evidence_synthesis,
        method_design=method_design,
        report=report,
    )
