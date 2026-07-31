from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TerminalState(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    TIMEOUT = "TIMEOUT"


class FailureType(StrEnum):
    WRONG_TOOL = "WRONG_TOOL"
    FORBIDDEN_TOOL = "FORBIDDEN_TOOL"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    MISSING_OUTPUT_FIELD = "MISSING_OUTPUT_FIELD"
    UNGROUNDED_CITATION = "UNGROUNDED_CITATION"
    TOOL_FAILURE = "TOOL_FAILURE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    MODEL_FAILURE = "MODEL_FAILURE"
    LOOP_DETECTED = "LOOP_DETECTED"
    STEP_LIMIT_EXCEEDED = "STEP_LIMIT_EXCEEDED"
    UNEXPECTED_GATE = "UNEXPECTED_GATE"
    MISSING_GATE = "MISSING_GATE"
    UNKNOWN = "UNKNOWN"


class ExpectedGate(StrictModel):
    required: bool = True
    reason: str = Field(min_length=1)
    action: str | None = None


class EvaluationCase(StrictModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,127}$")
    category: str = Field(min_length=1)
    input: str = Field(min_length=1)
    mode: Literal["offline", "live"] = "offline"
    status: Literal["active", "pending", "not_applicable"] = "active"
    expected_terminal_states: tuple[TerminalState, ...] = (TerminalState.COMPLETED,)
    required_tools: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    required_output_fields: tuple[str, ...] = ()
    citation_fields: tuple[str, ...] = ("source", "doi", "url", "paper_id")
    expected_gate: ExpectedGate | None = None
    max_steps: int = Field(default=12, ge=1, le=1000)
    max_tool_calls: int = Field(default=8, ge=0, le=1000)
    timeout_seconds: float = Field(default=120, gt=0, le=3600)
    max_output_chars: int = Field(default=100_000, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tool_policy(self) -> EvaluationCase:
        required, allowed, forbidden = map(
            set, (self.required_tools, self.allowed_tools, self.forbidden_tools)
        )
        if required & forbidden or allowed & forbidden:
            raise ValueError("required/allowed tools cannot also be forbidden")
        if allowed and not required <= allowed:
            raise ValueError(
                "required_tools must be a subset of allowed_tools when allowlist exists"
            )
        if (
            self.expected_gate
            and self.expected_gate.required
            and TerminalState.WAITING_APPROVAL not in self.expected_terminal_states
        ):
            raise ValueError("a required gate must expect WAITING_APPROVAL")
        return self


class StepRecord(StrictModel):
    step_index: int = Field(ge=0)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    result_summary: Any | None = None
    model_name: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    retry: bool = False
    error_type: str | None = None
    error: str | None = None
    gate_reason: str | None = None
    gate_action: str | None = None
    argument_valid: bool | None = None


class ExecutionTrajectory(StrictModel):
    run_id: str
    case_id: str
    started_at: datetime
    ended_at: datetime
    terminal_state: TerminalState
    user_input: str
    steps: tuple[StepRecord, ...] = ()
    final_output: Any | None = None
    stop_reason: str | None = None
    provider: str | None = None
    estimated_cost: float | None = Field(default=None, ge=0)
    cost_status: Literal["available", "unknown", "not_available"] = "not_available"


class JudgeResult(StrictModel):
    passed: bool
    checks: dict[str, bool | int | float | str | None]
    failures: tuple[FailureType, ...] = ()
    reasons: tuple[str, ...] = ()


class LLMJudgeResult(StrictModel):
    prompt_version: Literal["agent-eval-judge.v1"] = "agent-eval-judge.v1"
    relevance: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    faithfulness: int = Field(ge=1, le=5)
    instruction_following: int = Field(ge=1, le=5)
    passed: bool
    reason: str


class EvaluationResult(StrictModel):
    case: EvaluationCase
    trajectory: ExecutionTrajectory | None = None
    rule_judge: JudgeResult | None = None
    llm_judge: LLMJudgeResult | None = None
    llm_judge_error: str | None = None
    status: Literal["passed", "failed", "waiting_approval", "unverified"]
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
