from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from evaluation.recorder import canonical_call
from evaluation.schemas import (
    EvaluationCase,
    ExecutionTrajectory,
    FailureType,
    JudgeResult,
    TerminalState,
)

_IDENTIFIER = re.compile(r"(?:10\.\d{4,9}/[-._;()/:A-Z0-9]+|https?://\S+)", re.I)
_PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|lorem ipsum)\b", re.I)


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _field_values(value: Any, field: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, Mapping):
        if field in value:
            found.append(value[field])
        for nested in value.values():
            found.extend(_field_values(nested, field))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for nested in value:
            found.extend(_field_values(nested, field))
    return found


def _citation_tokens(value: Any, fields: tuple[str, ...]) -> set[str]:
    tokens: set[str] = set()
    for field in fields:
        for item in _field_values(value, field):
            if isinstance(item, str) and item.strip():
                tokens.add(item.strip().rstrip(".,)"))
    if isinstance(value, str):
        tokens.update(match.rstrip(".,)") for match in _IDENTIFIER.findall(value))
    return tokens


def judge(case: EvaluationCase, trajectory: ExecutionTrajectory) -> JudgeResult:
    tool_steps = [step for step in trajectory.steps if step.tool_name]
    calls = [step.tool_name for step in tool_steps if step.tool_name]
    required_coverage = (
        len(set(case.required_tools) & set(calls)) / len(case.required_tools)
        if case.required_tools
        else 1.0
    )
    forbidden_count = sum(name in case.forbidden_tools for name in calls)
    outside_allowlist = sum(
        bool(case.allowed_tools) and name not in case.allowed_tools for name in calls
    )
    invalid_count = sum(step.argument_valid is False for step in tool_steps)
    signatures = [canonical_call(step.tool_name or "", step.arguments) for step in tool_steps]
    duplicate_count = sum(max(count - 1, 0) for count in Counter(signatures).values())
    consecutive = any(
        signatures[i : i + 3].count(signatures[i]) == 3 for i in range(max(0, len(signatures) - 2))
    )
    window_loop = any(count >= 3 for count in Counter(signatures[-8:]).values())
    states = [step.state for step in trajectory.steps if step.state]
    state_loop = len(states) >= 4 and states[-4:-2] == states[-2:]
    loop_detected = consecutive or window_loop or state_loop
    step_exceeded = len(trajectory.steps) > case.max_steps
    tool_exceeded = len(tool_steps) > case.max_tool_calls

    output = trajectory.final_output
    output_non_empty = _present(output)
    required_values = {field: _field_values(output, field) for field in case.required_output_fields}
    completed_fields = sum(any(_present(v) for v in values) for values in required_values.values())
    completion_rate = (
        completed_fields / len(case.required_output_fields) if case.required_output_fields else 1.0
    )
    output_text = str(output or "")
    schema_valid = isinstance(output, Mapping | Sequence) and not isinstance(output, str)
    if not case.required_output_fields:
        schema_valid = output_non_empty
    output_citations = _citation_tokens(output, case.citation_fields)
    evidence: set[str] = set()
    for step in tool_steps:
        evidence.update(_citation_tokens(step.result_summary, case.citation_fields))
    unsupported = output_citations - evidence
    citation_presence_rate = 1.0 if output_citations else 0.0
    citation_grounding_rate = (
        len(output_citations - unsupported) / len(output_citations) if output_citations else 1.0
    )

    gate_steps = [step for step in trajectory.steps if step.event_type == "human_gate"]
    gate_expectation = case.expected_gate
    expected_gate = bool(gate_expectation and gate_expectation.required)
    gate_triggered = bool(gate_steps)
    reason_match = (
        True
        if gate_expectation is None
        else not expected_gate
        or any(step.gate_reason == gate_expectation.reason for step in gate_steps)
    )
    action_match = (
        True
        if gate_expectation is None
        else not expected_gate
        or gate_expectation.action is None
        or any(step.gate_action == gate_expectation.action for step in gate_steps)
    )
    waiting = trajectory.terminal_state == TerminalState.WAITING_APPROVAL
    gate_ok = (expected_gate and gate_triggered and waiting and reason_match and action_match) or (
        not expected_gate and not gate_triggered and not waiting
    )
    terminal_ok = trajectory.terminal_state in case.expected_terminal_states
    approval_pause = expected_gate and gate_triggered and waiting

    failures: list[FailureType] = []
    reasons: list[str] = []
    checks: dict[str, bool | int | float | str | None] = {
        "terminal_state": trajectory.terminal_state.value,
        "terminal_matches": terminal_ok,
        "required_tool_coverage": required_coverage,
        "forbidden_tool_call_count": forbidden_count,
        "unnecessary_tool_call_count": outside_allowlist,
        "invalid_argument_count": invalid_count,
        "duplicate_tool_call_count": duplicate_count,
        "loop_detected": loop_detected,
        "step_limit_exceeded": step_exceeded,
        "tool_call_limit_exceeded": tool_exceeded,
        "output_non_empty": output_non_empty,
        "schema_valid": schema_valid,
        "required_field_completion_rate": completion_rate,
        "citation_presence_rate": citation_presence_rate,
        "citation_grounding_rate": citation_grounding_rate,
        "unsupported_citation_count": len(unsupported),
        "output_limit_exceeded": len(output_text) > case.max_output_chars,
        "placeholder_detected": bool(_PLACEHOLDER.search(output_text)),
        "gate_triggered": gate_triggered,
        "gate_trigger_count": len(gate_steps),
        "expected_gate_triggered": expected_gate and gate_triggered,
        "unexpected_gate_triggered": not expected_gate and gate_triggered,
        "gate_reason_match": reason_match,
        "gate_action_match": action_match,
        "final_state_waiting_approval": waiting,
    }

    def fail(condition: bool, failure: FailureType, reason: str) -> None:
        if condition:
            failures.append(failure)
            reasons.append(reason)

    fail(required_coverage < 1, FailureType.WRONG_TOOL, "required tool was not called")
    fail(forbidden_count > 0, FailureType.FORBIDDEN_TOOL, "forbidden tool was called")
    fail(outside_allowlist > 0, FailureType.WRONG_TOOL, "tool was outside the allowlist")
    fail(invalid_count > 0, FailureType.INVALID_ARGUMENT, "tool arguments failed schema validation")
    fail(loop_detected, FailureType.LOOP_DETECTED, "repeated call/state loop detected")
    fail(
        step_exceeded or tool_exceeded, FailureType.STEP_LIMIT_EXCEEDED, "execution budget exceeded"
    )
    fail(
        not approval_pause and (not output_non_empty or completion_rate < 1),
        FailureType.MISSING_OUTPUT_FIELD,
        "output incomplete",
    )
    fail(bool(unsupported), FailureType.UNGROUNDED_CITATION, "citation absent from tool evidence")
    fail(
        expected_gate and not gate_ok,
        FailureType.MISSING_GATE,
        "expected gate missing or mismatched",
    )
    fail(
        not expected_gate and not gate_ok, FailureType.UNEXPECTED_GATE, "unexpected gate triggered"
    )
    fail(not terminal_ok, FailureType.UNKNOWN, "unexpected terminal state")
    tool_errors = [step for step in tool_steps if step.error_type]
    model_errors = [
        step
        for step in trajectory.steps
        if step.error_type and step.event_type.startswith(("model", "llm"))
    ]
    fail(
        any(step.error_type in {"TimeoutError", "TOOL_TIMEOUT"} for step in tool_errors),
        FailureType.TOOL_TIMEOUT,
        "tool timed out",
    )
    fail(bool(tool_errors), FailureType.TOOL_FAILURE, "tool call failed")
    fail(bool(model_errors), FailureType.MODEL_FAILURE, "model call failed")
    hard_output_failure = len(output_text) > case.max_output_chars or bool(
        _PLACEHOLDER.search(output_text)
    )
    passed = not failures and not hard_output_failure and (schema_valid or approval_pause)
    if hard_output_failure:
        reasons.append("output length or placeholder rule failed")
    return JudgeResult(
        passed=passed,
        checks=checks,
        failures=tuple(dict.fromkeys(failures)),
        reasons=tuple(reasons),
    )
