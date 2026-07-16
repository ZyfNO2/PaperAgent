from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from paperagent.schemas.base import FrozenModel
from paperagent.schemas.request import ResearchRequest

JsonObject = dict[str, Any]


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.CANCELLED, TaskStatus.SUCCEEDED, TaskStatus.FAILED}
)


class TaskError(FrozenModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False


class TaskCreateRequest(FrozenModel):
    request: ResearchRequest
    metadata: dict[str, str] = Field(default_factory=dict)


class TaskRecord(FrozenModel):
    task_id: str
    idempotency_key: str
    request: ResearchRequest
    request_hash: str
    metadata: dict[str, str] = Field(default_factory=dict)
    status: TaskStatus
    cancel_requested: bool = False
    result: JsonObject | None = None
    error: TaskError | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    event_cursor: int = 0


class TaskAccepted(FrozenModel):
    task_id: str
    status: TaskStatus
    reused: bool


class TaskView(FrozenModel):
    task_id: str
    status: TaskStatus
    cancel_requested: bool
    request: ResearchRequest
    metadata: dict[str, str] = Field(default_factory=dict)
    result: JsonObject | None = None
    error: TaskError | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    event_cursor: int

    @classmethod
    def from_record(cls, record: TaskRecord) -> TaskView:
        return cls(
            task_id=record.task_id,
            status=record.status,
            cancel_requested=record.cancel_requested,
            request=record.request,
            metadata=record.metadata,
            result=record.result,
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            event_cursor=record.event_cursor,
        )


class TaskEvent(FrozenModel):
    task_id: str
    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=120)
    payload: JsonObject = Field(default_factory=dict)
    created_at: datetime


class TaskEventPage(FrozenModel):
    task_id: str
    events: list[TaskEvent]
    next_cursor: int = Field(ge=0)
    terminal: bool


class CancelTaskResponse(FrozenModel):
    task_id: str
    status: TaskStatus
    accepted: bool


class HealthResponse(FrozenModel):
    status: str = "ok"
    api_contract: str = "v0.3"
