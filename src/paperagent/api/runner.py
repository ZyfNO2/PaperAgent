from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from paperagent.api.executor import TaskCancelledError, TaskExecutor
from paperagent.api.models import JsonObject, TaskError
from paperagent.api.repository import SQLiteTaskRepository

MAX_RESULT_BYTES = 180_000


@dataclass
class SingleProcessTaskRunner:
    repository: SQLiteTaskRepository
    executor: TaskExecutor
    idle_poll_seconds: float = 0.25
    _wake: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _worker: asyncio.Task[None] | None = field(default=None, init=False)
    _stopping: bool = field(default=False, init=False)

    async def start(self) -> None:
        if self._worker is not None:
            return
        await asyncio.to_thread(self.repository.recover_inflight_tasks)
        self._stopping = False
        self._worker = asyncio.create_task(self._run_loop(), name="paperagent-task-runner")
        if await asyncio.to_thread(self.repository.has_queued_tasks):
            self._wake.set()

    async def stop(self) -> None:
        worker = self._worker
        if worker is None:
            return
        self._stopping = True
        self._wake.set()
        await worker
        self._worker = None

    def notify(self) -> None:
        self._wake.set()

    async def _run_loop(self) -> None:
        while not self._stopping:
            record = await asyncio.to_thread(self.repository.claim_next_task)
            if record is not None:
                await self._execute(record.task_id, record.request)
                continue

            self._wake.clear()
            if await asyncio.to_thread(self.repository.has_queued_tasks):
                self._wake.set()
                continue
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.idle_poll_seconds)
            except TimeoutError:
                pass

    async def _execute(self, task_id: str, request: object) -> None:
        from paperagent.schemas.request import ResearchRequest

        typed_request = ResearchRequest.model_validate(request)
        if await asyncio.to_thread(self.repository.should_cancel, task_id):
            await asyncio.to_thread(self.repository.mark_cancelled, task_id)
            return

        async def emit(event_type: str, payload: JsonObject) -> None:
            await asyncio.to_thread(
                self.repository.append_event,
                task_id=task_id,
                event_type=event_type,
                payload=payload,
            )

        def should_cancel() -> bool:
            return self.repository.should_cancel(task_id)

        try:
            result = await self.executor.execute(
                task_id=task_id,
                request=typed_request,
                emit=emit,
                should_cancel=should_cancel,
            )
            if should_cancel():
                await asyncio.to_thread(self.repository.mark_cancelled, task_id)
                return
            encoded = json.dumps(
                result, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            if len(encoded) > MAX_RESULT_BYTES:
                await asyncio.to_thread(
                    self.repository.fail_task,
                    task_id,
                    TaskError(
                        code="RESULT_TOO_LARGE",
                        message="Task result exceeds the 180 KB MVP response limit.",
                        retryable=False,
                    ),
                )
                return
            await asyncio.to_thread(self.repository.complete_task, task_id, result)
        except TaskCancelledError:
            await asyncio.to_thread(self.repository.mark_cancelled, task_id)
        except Exception as exc:  # noqa: BLE001 - converted to a redacted durable error contract
            await asyncio.to_thread(
                self.repository.fail_task,
                task_id,
                TaskError(
                    code="EXECUTION_FAILED",
                    message=f"Task execution failed ({type(exc).__name__}).",
                    retryable=False,
                ),
            )
