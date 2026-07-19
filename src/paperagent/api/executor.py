from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from paperagent.api.models import JsonObject
from paperagent.runtime import RuntimeServices
from paperagent.schemas.request import ResearchRequest
from paperagent.state import PaperAgentState, state_to_primitive

EventEmitter = Callable[[str, JsonObject], Awaitable[None]]
CancellationProbe = Callable[[], bool]


class TaskCancelledError(RuntimeError):
    pass


class TaskBudgetExhaustedError(RuntimeError):
    pass


class TaskExecutor(Protocol):
    async def execute(
        self,
        *,
        task_id: str,
        request: ResearchRequest,
        emit: EventEmitter,
        should_cancel: CancellationProbe,
    ) -> JsonObject: ...


@dataclass(frozen=True)
class LangGraphTaskExecutor:
    """Run the existing PaperAgent graph behind the durable task contract.

    Cancellation is checked before execution by the runner and after each emitted graph state.
    Closing the async stream prevents later graph nodes from starting. A provider call already in
    progress cannot be forcefully interrupted by this MVP contract.
    """

    graph: Any
    services: RuntimeServices
    configurable: Mapping[str, Any] = field(default_factory=dict)

    async def execute(
        self,
        *,
        task_id: str,
        request: ResearchRequest,
        emit: EventEmitter,
        should_cancel: CancellationProbe,
    ) -> JsonObject:
        if should_cancel():
            raise TaskCancelledError("task cancelled before workflow execution")

        options = dict(self.configurable)
        options["services"] = self.services
        options["thread_id"] = task_id
        stream = self.graph.astream(
            {"request": request},
            {"configurable": options},
            stream_mode="values",
        )
        latest: PaperAgentState | None = None
        async for raw_state in stream:
            if isinstance(raw_state, Mapping):
                latest = cast(PaperAgentState, raw_state)
                primitive = state_to_primitive(latest)
                execution = primitive.get("execution")
                report = primitive.get("report")
                await emit(
                    "workflow.progress",
                    {
                        "execution_status": (
                            execution.get("status") if isinstance(execution, dict) else None
                        ),
                        "report_status": report.get("status") if isinstance(report, dict) else None,
                        "trace_count": len(primitive.get("trace", [])),
                    },
                )
                if isinstance(execution, dict):
                    last_error = execution.get("last_error")
                    if (
                        isinstance(last_error, dict)
                        and last_error.get("code") == "LLM_BUDGET_EXHAUSTED"
                    ):
                        close = getattr(stream, "aclose", None)
                        if close is not None:
                            await close()
                        raise TaskBudgetExhaustedError("workflow provider budget exhausted")
            if should_cancel():
                close = getattr(stream, "aclose", None)
                if close is not None:
                    await close()
                raise TaskCancelledError("task cancelled at a workflow boundary")

        if latest is None:
            raise RuntimeError("workflow completed without emitting state")
        result = state_to_primitive(latest)
        execution = result.get("execution")
        if not isinstance(execution, dict) or execution.get("status") not in {
            "completed",
            "blocked",
            "failed",
        }:
            raise RuntimeError("workflow completed without a terminal execution status")
        report = result.get("report")
        if execution.get("status") in {"completed", "blocked"} and not isinstance(report, dict):
            raise RuntimeError("terminal workflow state is missing report")
        return result
