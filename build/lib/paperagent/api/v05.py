from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from paperagent.api.diagnostics import (
    collect_runtime_diagnostics,
    ensure_schema_version,
    render_prometheus_metrics,
)
from paperagent.api.executor import TaskExecutor
from paperagent.api.repository import SQLiteTaskRepository
from paperagent.api.review import SQLiteReviewRepository
from paperagent.api.runner import SingleProcessTaskRunner
from paperagent.api.v04 import create_app as create_review_app
from paperagent.release import release_readiness
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
    app.version = "0.5.1"
    register_web_routes(app)
    durable_path = app.state.task_repository.database_path
    ensure_schema_version(durable_path)

    @app.get("/v1/diagnostics/runtime", include_in_schema=False)
    async def runtime_diagnostics() -> JSONResponse:
        snapshot = await asyncio.to_thread(collect_runtime_diagnostics, durable_path)
        return JSONResponse(content=snapshot)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        snapshot = await asyncio.to_thread(collect_runtime_diagnostics, durable_path)
        return PlainTextResponse(
            render_prometheus_metrics(snapshot),
            media_type="text/plain; version=0.0.4",
        )

    @app.get("/readyz", include_in_schema=False)
    async def readiness() -> JSONResponse:
        snapshot = await asyncio.to_thread(
            release_readiness,
            app.state.task_repository.database_path,
        )
        executor_readiness = getattr(executor, "readiness", None)
        if callable(executor_readiness):
            try:
                value = executor_readiness()
                if not isinstance(value, Mapping):
                    raise TypeError("executor readiness must return a mapping")
                snapshot["checks"]["executor"] = dict(value)
            except Exception as exc:
                snapshot["checks"]["executor"] = {
                    "ok": False,
                    "error": type(exc).__name__,
                }
        schema = await asyncio.to_thread(ensure_schema_version, durable_path)
        snapshot["checks"]["schema"] = {
            "ok": True,
            "version": schema["current_version"],
        }
        snapshot["status"] = (
            "ready"
            if all(bool(check.get("ok")) for check in snapshot["checks"].values())
            else "not_ready"
        )
        status_code = 200 if snapshot["status"] == "ready" else 503
        return JSONResponse(content=snapshot, status_code=status_code)

    return app
