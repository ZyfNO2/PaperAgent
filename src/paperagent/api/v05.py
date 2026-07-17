from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from paperagent.api.executor import TaskExecutor
from paperagent.api.repository import SQLiteTaskRepository
from paperagent.api.review import SQLiteReviewRepository
from paperagent.api.runner import SingleProcessTaskRunner
from paperagent.api.v04 import create_app as create_review_app
from paperagent.web import register_web_routes


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
    app = create_review_app(
        executor=executor,
        database_path=database_path,
        repository=repository,
        runner=runner,
        review_repository=review_repository,
        sse_poll_seconds=sse_poll_seconds,
        sse_heartbeat_seconds=sse_heartbeat_seconds,
    )
    app.version = "0.5.0"
    register_web_routes(app)
    return app
