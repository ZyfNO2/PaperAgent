"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.projects import router as projects_router
from app.db.database import init_db


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TopicPilot-CN",
        version="0.1.0",
        description="中国研究生开题选题助手 Phase 01 后端骨架。",
        lifespan=_lifespan,
    )

    # MVP: 允许 apps/web dev server (18182) 跨域调后端 (18181)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:18182",
            "http://localhost:18182",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects_router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "phase": "01"}

    return app


app = create_app()
