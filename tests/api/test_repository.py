from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from paperagent.api.models import TaskCreateRequest, TaskError, TaskStatus
from paperagent.api.repository import (
    IdempotencyConflictError,
    SQLiteTaskRepository,
    TaskNotFoundError,
    task_ids,
)
from paperagent.schemas import ResearchRequest

NOW = datetime(2026, 7, 17, tzinfo=UTC)


def _payload(question: str = "Evaluate retrieval reliability") -> TaskCreateRequest:
    return TaskCreateRequest(
        request=ResearchRequest(question=question),
        metadata={"client": "test"},
    )


def _repository(tmp_path) -> SQLiteTaskRepository:
    return SQLiteTaskRepository(tmp_path / "tasks.db")


def test_repository__create_get_and_idempotent_replay(tmp_path) -> None:
    repository = _repository(tmp_path)
    created, reused = repository.create_task(
        task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW
    )
    replayed, replay_reused = repository.create_task(
        task_id="ignored", idempotency_key="idem-1", payload=_payload(), now=NOW
    )

    assert reused is False
    assert replay_reused is True
    assert replayed.task_id == created.task_id == "task-1"
    assert repository.get_task("task-1").status is TaskStatus.QUEUED
    assert task_ids([created, replayed]) == ["task-1", "task-1"]
    events = repository.list_events("task-1")
    assert [(event.sequence, event.event_type) for event in events] == [(1, "task.queued")]
    assert created.event_cursor == 1


def test_repository__idempotency_key_conflict_is_fail_closed(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW)

    with pytest.raises(IdempotencyConflictError):
        repository.create_task(
            task_id="task-2",
            idempotency_key="idem-1",
            payload=_payload("A different research question"),
            now=NOW,
        )


def test_repository__claim_append_and_complete(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW)

    claimed = repository.claim_next_task(now=NOW + timedelta(seconds=1))
    assert claimed is not None
    assert claimed.status is TaskStatus.RUNNING
    assert claimed.started_at == NOW + timedelta(seconds=1)
    progress = repository.append_event(
        task_id="task-1",
        event_type="workflow.progress",
        payload={"node": "planning"},
        now=NOW + timedelta(seconds=2),
    )
    assert progress.sequence == 3

    completed = repository.complete_task(
        "task-1", {"report": {"status": "completed"}}, now=NOW + timedelta(seconds=3)
    )
    assert completed.status is TaskStatus.SUCCEEDED
    assert completed.result == {"report": {"status": "completed"}}
    assert completed.finished_at == NOW + timedelta(seconds=3)
    assert repository.claim_next_task(now=NOW) is None
    assert repository.has_queued_tasks() is False
    assert [event.event_type for event in repository.list_events("task-1", after_sequence=1)] == [
        "task.started",
        "workflow.progress",
        "task.succeeded",
    ]


def test_repository__queued_cancel_never_becomes_running(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW)

    cancelled, accepted = repository.request_cancel("task-1", now=NOW + timedelta(seconds=1))
    repeated, repeated_accepted = repository.request_cancel(
        "task-1", now=NOW + timedelta(seconds=2)
    )

    assert accepted is True
    assert repeated_accepted is False
    assert cancelled.status is repeated.status is TaskStatus.CANCELLED
    assert cancelled.cancel_requested is True
    assert repository.claim_next_task(now=NOW) is None


def test_repository__running_cancel_is_cooperative_then_terminal(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW)
    assert repository.claim_next_task(now=NOW) is not None

    requested, accepted = repository.request_cancel("task-1", now=NOW + timedelta(seconds=1))
    assert accepted is True
    assert requested.status is TaskStatus.CANCEL_REQUESTED
    assert repository.should_cancel("task-1") is True

    cancelled = repository.mark_cancelled("task-1", now=NOW + timedelta(seconds=2))
    assert cancelled.status is TaskStatus.CANCELLED
    terminal, terminal_accepted = repository.request_cancel("task-1", now=NOW)
    assert terminal.status is TaskStatus.CANCELLED
    assert terminal_accepted is False


def test_repository__failure_and_restart_recovery_are_durable(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW)
    repository.create_task(task_id="task-2", idempotency_key="idem-2", payload=_payload(), now=NOW)
    first = repository.claim_next_task(now=NOW)
    second = repository.claim_next_task(now=NOW)
    assert first is not None and second is not None
    repository.request_cancel(second.task_id, now=NOW)

    recovered = repository.recover_inflight_tasks(now=NOW + timedelta(minutes=1))
    assert recovered == 2
    for task_id in (first.task_id, second.task_id):
        record = repository.get_task(task_id)
        assert record.status is TaskStatus.FAILED
        assert record.error is not None
        assert record.error.code == "PROCESS_RESTARTED"
        assert record.error.retryable is True

    repository.create_task(task_id="task-3", idempotency_key="idem-3", payload=_payload(), now=NOW)
    failed = repository.fail_task(
        "task-3",
        TaskError(code="UPSTREAM", message="Provider unavailable", retryable=True),
        now=NOW,
    )
    assert failed.status is TaskStatus.FAILED
    assert failed.error is not None and failed.error.code == "UPSTREAM"


def test_repository__validation_and_missing_task_paths(tmp_path) -> None:
    repository = _repository(tmp_path)
    with pytest.raises(TaskNotFoundError):
        repository.get_task("missing")
    with pytest.raises(TaskNotFoundError):
        repository.list_events("missing")
    with pytest.raises(TaskNotFoundError):
        repository.append_event(task_id="missing", event_type="x", payload={})
    with pytest.raises(TaskNotFoundError):
        repository.request_cancel("missing")
    with pytest.raises(ValueError):
        repository.list_events("missing", after_sequence=-1)
    with pytest.raises(ValueError):
        repository.list_events("missing", limit=0)

    repository.create_task(task_id="task-1", idempotency_key="idem-1", payload=_payload(), now=NOW)
    with pytest.raises(ValueError, match="16 KiB"):
        repository.append_event(
            task_id="task-1",
            event_type="oversized",
            payload={"content": "x" * 20_000},
        )
