from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from paperagent.api.executor import (
    LangGraphTaskExecutor,
    TaskBudgetExhaustedError,
    TaskCancelledError,
)
from paperagent.api.models import TaskCreateRequest, TaskStatus
from paperagent.api.repository import SQLiteTaskRepository
from paperagent.api.runner import SingleProcessTaskRunner
from paperagent.schemas import ResearchRequest


class RecordingExecutor:
    def __init__(self, *, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result or {"report": {"status": "completed"}}
        self.error = error
        self.calls: list[str] = []

    async def execute(self, *, task_id, request, emit, should_cancel):
        self.calls.append(task_id)
        await emit("workflow.progress", {"question": request.question})
        if self.error is not None:
            raise self.error
        if should_cancel():
            raise TaskCancelledError("cancelled")
        return self.result


class CooperativeExecutor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.calls: list[str] = []

    async def execute(self, *, task_id, request, emit, should_cancel):
        self.calls.append(task_id)
        self.started.set()
        await emit("workflow.progress", {"phase": "started"})
        while not should_cancel():
            await asyncio.sleep(0.01)
        raise TaskCancelledError("cancelled at boundary")


def _payload() -> TaskCreateRequest:
    return TaskCreateRequest(request=ResearchRequest(question="Evaluate retrieval reliability"))


async def _wait_for_terminal(repository: SQLiteTaskRepository, task_id: str) -> TaskStatus:
    for _ in range(200):
        status = repository.get_task(task_id).status
        if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return status
        await asyncio.sleep(0.01)
    raise AssertionError("task did not reach a terminal state")


@pytest.mark.asyncio
async def test_runner__executes_queued_task_and_persists_events(tmp_path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    executor = RecordingExecutor()
    runner = SingleProcessTaskRunner(repository, executor, idle_poll_seconds=0.01)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload())

    await runner.start()
    await runner.start()
    runner.notify()
    assert await _wait_for_terminal(repository, "task-1") is TaskStatus.SUCCEEDED
    await runner.stop()
    await runner.stop()

    assert executor.calls == ["task-1"]
    assert repository.get_task("task-1").result == {"report": {"status": "completed"}}
    assert [event.event_type for event in repository.list_events("task-1")] == [
        "task.queued",
        "task.started",
        "workflow.progress",
        "task.succeeded",
    ]


@pytest.mark.asyncio
async def test_runner__redacts_executor_exception_text(tmp_path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    executor = RecordingExecutor(error=RuntimeError("secret-token-value"))
    runner = SingleProcessTaskRunner(repository, executor, idle_poll_seconds=0.01)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload())

    await runner.start()
    runner.notify()
    assert await _wait_for_terminal(repository, "task-1") is TaskStatus.FAILED
    await runner.stop()

    error = repository.get_task("task-1").error
    assert error is not None
    assert error.code == "EXECUTION_FAILED"
    assert "RuntimeError" in error.message
    assert "secret-token-value" not in error.message


@pytest.mark.asyncio
async def test_runner__rejects_oversized_result(tmp_path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    executor = RecordingExecutor(result={"content": "x" * 181_000})
    runner = SingleProcessTaskRunner(repository, executor, idle_poll_seconds=0.01)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload())

    await runner.start()
    runner.notify()
    assert await _wait_for_terminal(repository, "task-1") is TaskStatus.FAILED
    await runner.stop()

    error = repository.get_task("task-1").error
    assert error is not None and error.code == "RESULT_TOO_LARGE"


@pytest.mark.asyncio
async def test_runner__queued_cancel_prevents_executor_call(tmp_path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    executor = RecordingExecutor()
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload())
    repository.request_cancel("task-1")
    runner = SingleProcessTaskRunner(repository, executor, idle_poll_seconds=0.01)

    await runner.start()
    runner.notify()
    await asyncio.sleep(0.03)
    await runner.stop()

    assert executor.calls == []
    assert repository.get_task("task-1").status is TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_runner__running_cancel_is_observed_cooperatively(tmp_path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    executor = CooperativeExecutor()
    runner = SingleProcessTaskRunner(repository, executor, idle_poll_seconds=0.01)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload())

    await runner.start()
    runner.notify()
    await asyncio.wait_for(executor.started.wait(), timeout=1)
    repository.request_cancel("task-1")
    assert await _wait_for_terminal(repository, "task-1") is TaskStatus.CANCELLED
    await runner.stop()

    assert executor.calls == ["task-1"]


class FakeGraph:
    def __init__(self, states: list[dict]) -> None:
        self.states = states
        self.config = None

    async def astream(self, initial_state, config, stream_mode) -> AsyncIterator[dict]:
        self.config = config
        assert initial_state["request"].question == "Evaluate retrieval reliability"
        assert stream_mode == "values"
        for state in self.states:
            yield state


@pytest.mark.asyncio
async def test_langgraph_executor__streams_progress_and_returns_primitive_state() -> None:
    graph = FakeGraph(
        [
            {"request": ResearchRequest(question="Evaluate retrieval reliability"), "trace": []},
            {
                "request": ResearchRequest(question="Evaluate retrieval reliability"),
                "execution": {"status": "completed"},
                "report": {
                    "status": "completed",
                    "executive_summary": "done",
                    "verified_findings": [],
                    "inferred_findings": [],
                    "limitations": ["bounded test"],
                },
                "trace": [],
            },
        ]
    )
    services = SimpleNamespace()
    executor = LangGraphTaskExecutor(graph=graph, services=services, configurable={"scenario": "x"})
    emitted: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> None:
        emitted.append((event_type, payload))

    result = await executor.execute(
        task_id="task-1",
        request=ResearchRequest(question="Evaluate retrieval reliability"),
        emit=emit,
        should_cancel=lambda: False,
    )

    assert result["request"]["question"] == "Evaluate retrieval reliability"
    assert len(emitted) == 2
    assert graph.config["configurable"]["thread_id"] == "task-1"
    assert graph.config["configurable"]["scenario"] == "x"


@pytest.mark.asyncio
async def test_langgraph_executor__fails_closed_on_nonterminal_state() -> None:
    graph = FakeGraph(
        [{"request": ResearchRequest(question="Evaluate retrieval reliability"), "trace": []}]
    )
    executor = LangGraphTaskExecutor(graph=graph, services=SimpleNamespace())

    async def emit(event_type: str, payload: dict) -> None:
        del event_type, payload

    with pytest.raises(RuntimeError, match="terminal execution status"):
        await executor.execute(
            task_id="task-1",
            request=ResearchRequest(question="Evaluate retrieval reliability"),
            emit=emit,
            should_cancel=lambda: False,
        )


@pytest.mark.asyncio
async def test_langgraph_executor__fails_closed_on_provider_budget_exhaustion() -> None:
    graph = FakeGraph(
        [
            {
                "request": ResearchRequest(question="Evaluate retrieval reliability"),
                "execution": {
                    "status": "failed",
                    "last_error": {
                        "code": "LLM_BUDGET_EXHAUSTED",
                        "message": "budget exhausted",
                        "node": "planning_node",
                    },
                },
                "trace": [],
            }
        ]
    )
    executor = LangGraphTaskExecutor(graph=graph, services=SimpleNamespace())

    async def emit(event_type: str, payload: dict) -> None:
        del event_type, payload

    with pytest.raises(TaskBudgetExhaustedError, match="budget exhausted"):
        await executor.execute(
            task_id="task-1",
            request=ResearchRequest(question="Evaluate retrieval reliability"),
            emit=emit,
            should_cancel=lambda: False,
        )


@pytest.mark.asyncio
async def test_langgraph_executor__cancelled_before_start_and_empty_stream_fail() -> None:
    services = SimpleNamespace()
    executor = LangGraphTaskExecutor(graph=FakeGraph([]), services=services)

    async def emit(event_type: str, payload: dict) -> None:
        del event_type, payload

    with pytest.raises(TaskCancelledError):
        await executor.execute(
            task_id="task-1",
            request=ResearchRequest(question="Evaluate retrieval reliability"),
            emit=emit,
            should_cancel=lambda: True,
        )
    with pytest.raises(RuntimeError, match="without emitting state"):
        await executor.execute(
            task_id="task-1",
            request=ResearchRequest(question="Evaluate retrieval reliability"),
            emit=emit,
            should_cancel=lambda: False,
        )


@pytest.mark.asyncio
async def test_langgraph_executor__cancelled_after_state_closes_stream() -> None:
    graph = FakeGraph(
        [{"request": ResearchRequest(question="Evaluate retrieval reliability"), "trace": []}]
    )
    executor = LangGraphTaskExecutor(graph=graph, services=SimpleNamespace())
    calls = 0

    def should_cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    async def emit(event_type: str, payload: dict) -> None:
        del event_type, payload

    with pytest.raises(TaskCancelledError, match="workflow boundary"):
        await executor.execute(
            task_id="task-1",
            request=ResearchRequest(question="Evaluate retrieval reliability"),
            emit=emit,
            should_cancel=should_cancel,
        )
