import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from evaluation.adapters.agent_adapter import (
    CallableAgentAdapter,
    OfflineFixtureAdapter,
    ToolSchemaRegistry,
)
from evaluation.recorder import summarize
from evaluation.report import write_report
from evaluation.runner import run_cases
from evaluation.schemas import EvaluationCase


@pytest.mark.asyncio
async def test_exception_isolated_and_other_case_continues() -> None:
    bad = EvaluationCase(
        case_id="bad_001",
        category="x",
        input="x",
        metadata={"offline_observation": {"raise": "boom"}},
    )
    good = EvaluationCase(
        case_id="good_001",
        category="x",
        input="x",
        metadata={"offline_observation": {"final_output": {"ok": True}}},
    )
    results = await run_cases((bad, good), OfflineFixtureAdapter(), max_concurrency=2)
    assert [r.status for r in results] == ["failed", "passed"]


@pytest.mark.asyncio
async def test_missing_token_usage_is_not_fabricated() -> None:
    case = EvaluationCase(
        case_id="token_001",
        category="x",
        input="x",
        metadata={
            "offline_observation": {
                "steps": [{"event_type": "model_call"}],
                "final_output": {"ok": True},
            }
        },
    )
    result = (await run_cases((case,), OfflineFixtureAdapter()))[0]
    assert result.metrics["total_tokens"] == "not_available"
    assert result.metrics["estimated_cost"] == "not_available"


def test_secret_redaction_and_bounded_summary() -> None:
    result = summarize({"api_key": "secret", "header": "Bearer abc", "text": "x" * 3000})
    assert result["api_key"] == "[REDACTED]"
    assert "abc" not in result["header"]
    assert result["text"].endswith("[truncated]")


@pytest.mark.asyncio
async def test_report_generation(tmp_path: Path) -> None:
    case = EvaluationCase(
        case_id="report_001",
        category="x",
        input="x",
        metadata={"offline_observation": {"final_output": {"ok": True}}},
    )
    results = await run_cases((case,), OfflineFixtureAdapter())
    summary = write_report(tmp_path, "run-test", results)
    assert summary["case_count"] == 1
    assert (tmp_path / "summary.json").exists()
    assert "offline control-flow" in (tmp_path / "report.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "cases" / "report_001.json").read_text(encoding="utf-8"))
    assert payload["status"] == "passed"


@pytest.mark.asyncio
async def test_live_case_without_adapter_is_unverified() -> None:
    case = EvaluationCase(case_id="live_001", category="live", input="x", mode="live")
    result = (await run_cases((case,), OfflineFixtureAdapter()))[0]
    assert result.status == "unverified"
    assert result.error == "live adapter not configured"


class SearchArguments(BaseModel):
    query: str
    limit: int = Field(ge=1)


def test_tool_argument_validation_reuses_injected_schema() -> None:
    registry = ToolSchemaRegistry({"paper_search": SearchArguments})
    assert registry.validate("paper_search", {"query": "x", "limit": 1}) is True
    assert registry.validate("paper_search", {"query": "x", "limit": 0}) is False
    assert registry.validate("unregistered", {}) is None


@pytest.mark.asyncio
async def test_case_timeout_is_recorded_and_does_not_abort_batch() -> None:
    slow = EvaluationCase(
        case_id="slow_001",
        category="timeout",
        input="x",
        timeout_seconds=0.001,
        metadata={"offline_observation": {"delay_seconds": 0.05}},
    )
    good = EvaluationCase(
        case_id="after_timeout_001",
        category="x",
        input="x",
        metadata={"offline_observation": {"final_output": {"ok": True}}},
    )
    results = await run_cases((slow, good), OfflineFixtureAdapter())
    assert results[0].error == "evaluation case timed out"
    assert results[1].status == "passed"


class FailingJudge:
    async def generate_structured(self, **kwargs):
        raise RuntimeError("judge unavailable")


@pytest.mark.asyncio
async def test_llm_judge_failure_preserves_rule_result() -> None:
    case = EvaluationCase(
        case_id="judge_001",
        category="x",
        input="x",
        metadata={"offline_observation": {"final_output": {"ok": True}}},
    )
    result = (
        await run_cases(
            (case,),
            OfflineFixtureAdapter(),
            judge_provider=FailingJudge(),  # type: ignore[arg-type]
        )
    )[0]
    assert result.status == "passed"
    assert result.rule_judge is not None
    assert result.llm_judge_error == "RuntimeError: judge unavailable"


@pytest.mark.asyncio
async def test_production_interrupt_maps_to_waiting_approval_without_resume() -> None:
    calls = 0

    async def invoke(question: str):
        nonlocal calls
        calls += 1
        return {
            "execution": {"status": "running"},
            "trace": [],
            "__interrupt__": ({"source": "planning", "question": "Clarify scope"},),
        }

    case = EvaluationCase(
        case_id="interrupt_001",
        category="human_gate",
        input="ambiguous research request",
        expected_terminal_states=("WAITING_APPROVAL",),
        expected_gate={"reason": "planning", "action": "Clarify scope"},
    )
    result = await run_cases((case,), CallableAgentAdapter(invoke))
    assert result[0].status == "waiting_approval"
    assert calls == 1
