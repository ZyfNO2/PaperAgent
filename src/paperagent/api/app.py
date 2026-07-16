from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from paperagent.api.executor import TaskExecutor
from paperagent.api.models import (
    TERMINAL_TASK_STATUSES,
    CancelTaskResponse,
    HealthResponse,
    TaskAccepted,
    TaskCreateRequest,
    TaskEvent,
    TaskEventPage,
    TaskStatus,
    TaskView,
)
from paperagent.api.repository import (
    IdempotencyConflictError,
    SQLiteTaskRepository,
    TaskNotFoundError,
)
from paperagent.api.runner import SingleProcessTaskRunner


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(16)}"


def _sse_event(event: TaskEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.sequence}\nevent: {event.event_type}\ndata: {data}\n\n"


def create_app(
    *,
    executor: TaskExecutor,
    database_path: str | Path = "paperagent.db",
    repository: SQLiteTaskRepository | None = None,
    runner: SingleProcessTaskRunner | None = None,
    sse_poll_seconds: float = 0.2,
    sse_heartbeat_seconds: float = 15.0,
) -> FastAPI:
    task_repository = repository or SQLiteTaskRepository(database_path)
    task_runner = runner or SingleProcessTaskRunner(task_repository, executor)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await task_runner.start()
        try:
            yield
        finally:
            await task_runner.stop()

    app = FastAPI(
        title="PaperAgent Task API",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.state.task_repository = task_repository
    app.state.task_runner = task_runner

    @app.get("/healthz", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post(
        "/v1/tasks",
        response_model=TaskAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_task(
        payload: TaskCreateRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ) -> TaskAccepted:
        try:
            record, reused = await asyncio.to_thread(
                task_repository.create_task,
                task_id=_new_task_id(),
                idempotency_key=idempotency_key,
                payload=payload,
            )
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if record.status is TaskStatus.QUEUED:
            task_runner.notify()
        return TaskAccepted(task_id=record.task_id, status=record.status, reused=reused)

    @app.get("/v1/tasks/{task_id}", response_model=TaskView)
    async def get_task(task_id: str) -> TaskView:
        try:
            record = await asyncio.to_thread(task_repository.get_task, task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from exc
        return TaskView.from_record(record)

    @app.get("/v1/tasks/{task_id}/events", response_model=TaskEventPage)
    async def get_task_events(
        task_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> TaskEventPage:
        try:
            events = await asyncio.to_thread(
                task_repository.list_events,
                task_id,
                after_sequence=after,
                limit=limit,
            )
            record = await asyncio.to_thread(task_repository.get_task, task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from exc
        next_cursor = events[-1].sequence if events else after
        return TaskEventPage(
            task_id=task_id,
            events=events,
            next_cursor=next_cursor,
            terminal=record.status in TERMINAL_TASK_STATUSES,
        )

    @app.get("/v1/tasks/{task_id}/events/stream")
    async def stream_task_events(
        request: Request,
        task_id: str,
        after: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        try:
            await asyncio.to_thread(task_repository.get_task, task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from exc

        async def event_stream() -> AsyncIterator[str]:
            cursor = after
            last_heartbeat = time.monotonic()
            while True:
                if await request.is_disconnected():
                    return
                events = await asyncio.to_thread(
                    task_repository.list_events,
                    task_id,
                    after_sequence=cursor,
                    limit=100,
                )
                for event in events:
                    cursor = event.sequence
                    yield _sse_event(event)
                record = await asyncio.to_thread(task_repository.get_task, task_id)
                if record.status in TERMINAL_TASK_STATUSES and cursor >= record.event_cursor:
                    return
                now = time.monotonic()
                if now - last_heartbeat >= sse_heartbeat_seconds:
                    last_heartbeat = now
                    yield ": keep-alive\n\n"
                await asyncio.sleep(sse_poll_seconds)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/v1/tasks/{task_id}/cancel", response_model=CancelTaskResponse)
    async def cancel_task(task_id: str) -> CancelTaskResponse:
        try:
            record, accepted = await asyncio.to_thread(task_repository.request_cancel, task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from exc
        task_runner.notify()
        return CancelTaskResponse(task_id=task_id, status=record.status, accepted=accepted)

    return app
