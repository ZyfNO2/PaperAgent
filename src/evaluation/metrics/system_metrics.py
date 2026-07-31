from __future__ import annotations

from typing import Any

from evaluation.schemas import ExecutionTrajectory, JudgeResult


def collect_case_metrics(trajectory: ExecutionTrajectory, judge: JudgeResult) -> dict[str, Any]:
    model_steps = [s for s in trajectory.steps if s.event_type.startswith(("model", "llm"))]
    tool_steps = [s for s in trajectory.steps if s.tool_name]
    input_values = [s.input_tokens for s in model_steps if s.input_tokens is not None]
    output_values = [s.output_tokens for s in model_steps if s.output_tokens is not None]
    tokens_available = len(input_values) == len(model_steps) and len(output_values) == len(
        model_steps
    )
    input_tokens = sum(input_values) if tokens_available else "not_available"
    output_tokens = sum(output_values) if tokens_available else "not_available"
    failed_indexes = [index for index, step in enumerate(tool_steps) if step.error_type]
    recovered = sum(
        any(not later.error_type for later in tool_steps[index + 1 :]) for index in failed_indexes
    )
    timeout_count = sum(s.error_type in {"TimeoutError", "TOOL_TIMEOUT"} for s in trajectory.steps)
    return {
        "task_success": judge.passed,
        **judge.checks,
        "total_latency_ms": max(
            0, int((trajectory.ended_at - trajectory.started_at).total_seconds() * 1000)
        ),
        "model_latency_ms": sum(s.latency_ms or 0 for s in model_steps),
        "tool_latency_ms": sum(s.latency_ms or 0 for s in tool_steps),
        "model_call_count": len(model_steps),
        "tool_call_count": len(tool_steps),
        "retry_count": sum(s.retry for s in trajectory.steps),
        "timeout": timeout_count > 0,
        "timeout_count": timeout_count,
        "tool_failure_count": sum(bool(s.error_type) for s in tool_steps),
        "tool_failure_recovery_rate": (recovered / len(failed_indexes) if failed_indexes else 1.0),
        "unnecessary_tool_call_count": judge.checks.get("unnecessary_tool_call_count", 0),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": (
            input_tokens + output_tokens
            if isinstance(input_tokens, int) and isinstance(output_tokens, int)
            else "not_available"
        ),
        "estimated_cost": trajectory.estimated_cost
        if trajectory.cost_status == "available"
        else trajectory.cost_status,
    }
