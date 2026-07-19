from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from paperagent.api.app import create_app as create_task_app
from paperagent.api.executor import TaskExecutor
from paperagent.api.repository import SQLiteTaskRepository
from paperagent.api.review import SQLiteReviewRepository
from paperagent.api.review_routes import register_review_routes
from paperagent.api.runner import SingleProcessTaskRunner


def create_app(
    *,
    executor: TaskExecutor,
    database_path: str | Path = "paperagent.db",
    repository: SQLiteTaskRepository | None = None,
    runner: SingleProcessTaskRunner | None = None,
    review_repository: SQLiteReviewRepository | None = None,
    sse_poll_seconds: float = 0.2,
    sse_heartbeat_seconds: float = 15.0,
) -> FastAPI:
    task_repository = repository or SQLiteTaskRepository(database_path)
    app = create_task_app(
        executor=executor,
        database_path=database_path,
        repository=task_repository,
        runner=runner,
        sse_poll_seconds=sse_poll_seconds,
        sse_heartbeat_seconds=sse_heartbeat_seconds,
    )
    app.version = "0.4.0"
    durable_reviews = review_repository or SQLiteReviewRepository(task_repository)
    app.state.review_repository = durable_reviews
    register_review_routes(app, durable_reviews)
    return app
