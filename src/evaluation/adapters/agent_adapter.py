from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from evaluation.recorder import summarize
from evaluation.schemas import EvaluationCase, ExecutionTrajectory, StepRecord, TerminalState


class AgentAdapter(Protocol):
    async def run(self, case: EvaluationCase) -> ExecutionTrajectory: ...


ToolValidator = Callable[[Mapping[str, Any]], bool]


class ToolSchemaRegistry:
    """Delegates argument checks to production Pydantic/type schemas supplied by adapters."""

    def __init__(self, schemas: Mapping[str, Any] | None = None) -> None:
        self._schemas = dict(schemas or {})

    def validate(self, name: str, arguments: Mapping[str, Any]) -> bool | None:
        schema = self._schemas.get(name)
        if schema is None:
            return None
        try:
            if callable(schema) and not isinstance(schema, type):
                return bool(schema(arguments))
            TypeAdapter(schema).validate_python(arguments)
        except (ValidationError, TypeError, ValueError):
            return False
        return True


class OfflineFixtureAdapter:
    """Deterministic control-flow adapter. It is explicitly not a live/E2E agent run."""

    def __init__(self, *, tool_schemas: ToolSchemaRegistry | None = None) -> None:
        self.tool_schemas = tool_schemas or ToolSchemaRegistry()

    async def run(self, case: EvaluationCase) -> ExecutionTrajectory:
        started = datetime.now(UTC)
        fixture = case.metadata.get("offline_observation", {})
        if not isinstance(fixture, Mapping):
            raise ValueError("metadata.offline_observation must be an object")
        if fixture.get("raise"):
            raise RuntimeError(str(fixture["raise"]))
        delay = float(fixture.get("delay_seconds", 0))
        if delay:
            await asyncio.sleep(delay)
        raw_steps = fixture.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError("offline_observation.steps must be a list")
        steps: list[StepRecord] = []
        for index, raw in enumerate(raw_steps):
            if not isinstance(raw, Mapping):
                raise ValueError("each offline step must be an object")
            data = dict(raw)
            data.setdefault("step_index", index)
            data.setdefault("timestamp", started)
            arguments = data.get("arguments")
            tool_name = data.get("tool_name")
            if tool_name and isinstance(arguments, Mapping) and "argument_valid" not in data:
                data["argument_valid"] = self.tool_schemas.validate(str(tool_name), arguments)
            data["arguments"] = summarize(arguments) if arguments is not None else None
            data["result_summary"] = summarize(data.get("result_summary"))
            steps.append(StepRecord.model_validate(data))
        terminal = TerminalState(str(fixture.get("terminal_state", "COMPLETED")))
        return ExecutionTrajectory(
            run_id=f"eval-{uuid4().hex[:12]}",
            case_id=case.case_id,
            started_at=started,
            ended_at=datetime.now(UTC),
            terminal_state=terminal,
            user_input=str(summarize(case.input)),
            steps=tuple(steps),
            final_output=summarize(fixture.get("final_output")),
            stop_reason=fixture.get("stop_reason"),
            provider="offline_fixture",
            estimated_cost=None,
            cost_status="not_available",
        )


class CallableAgentAdapter:
    """Integration seam for the production graph/API without evaluation imports in agent code."""

    def __init__(self, invoke: Callable[[str], Awaitable[Mapping[str, Any]]]) -> None:
        self._invoke = invoke

    async def run(self, case: EvaluationCase) -> ExecutionTrajectory:
        started = datetime.now(UTC)
        result = await self._invoke(case.input)
        raw_execution = result.get("execution")
        status = (
            raw_execution.get("status")
            if isinstance(raw_execution, Mapping)
            else getattr(raw_execution, "status", None)
        )
        interrupts = result.get("__interrupt__", ())
        terminal = {
            "completed": TerminalState.COMPLETED,
            "waiting_human": TerminalState.WAITING_APPROVAL,
            "blocked": TerminalState.BLOCKED,
            "failed": TerminalState.FAILED,
        }.get(str(status), TerminalState.FAILED)
        if interrupts:
            terminal = TerminalState.WAITING_APPROVAL
        steps = []
        for index, event in enumerate(result.get("trace", ())):
            payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
            steps.append(
                StepRecord(
                    step_index=index,
                    event_type=str(payload.get("event_type", "agent_event")),
                    timestamp=payload.get("timestamp", started),
                    state=payload.get("status"),
                    model_name=payload.get("model_name"),
                    input_tokens=(payload.get("token_usage") or {}).get("input_tokens"),
                    output_tokens=(payload.get("token_usage") or {}).get("output_tokens"),
                    latency_ms=payload.get("duration_ms"),
                    error_type=payload.get("error_code"),
                )
            )
        action = (
            raw_execution.get("human_action_required")
            if isinstance(raw_execution, Mapping)
            else getattr(raw_execution, "human_action_required", None)
        )
        if action is None and interrupts:
            first = next(iter(interrupts))
            action = getattr(first, "value", first)
        if action is not None:
            if isinstance(action, Mapping):
                reason = str(action.get("source", "human_review"))
                question = str(action.get("question", "approval required"))
            else:
                reason = str(getattr(action, "source", "human_review"))
                question = str(getattr(action, "question", "approval required"))
            steps.append(
                StepRecord(
                    step_index=len(steps),
                    event_type="human_gate",
                    timestamp=datetime.now(UTC),
                    state="WAITING_APPROVAL",
                    gate_reason=reason,
                    gate_action=question,
                )
            )
        telemetry = result.get("provider_telemetry", ())
        known_costs: list[float] = []
        if isinstance(telemetry, Sequence) and not isinstance(telemetry, str | bytes):
            for record in telemetry:
                if not isinstance(record, Mapping):
                    continue
                usage = record.get("usage")
                if isinstance(usage, Mapping) and usage.get("estimated_cost_usd") is not None:
                    known_costs.append(float(usage["estimated_cost_usd"]))
        return ExecutionTrajectory(
            run_id=str(getattr(result.get("run"), "run_id", f"eval-{uuid4().hex[:12]}")),
            case_id=case.case_id,
            started_at=started,
            ended_at=datetime.now(UTC),
            terminal_state=terminal,
            user_input=str(summarize(case.input)),
            steps=tuple(steps),
            final_output=summarize(result.get("report") or result.get("final_output")),
            provider="paperagent_graph",
            estimated_cost=sum(known_costs) if known_costs else None,
            cost_status="available" if known_costs else "unknown",
        )
