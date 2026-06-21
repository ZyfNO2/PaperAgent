"""FastAPI 入口 — OneTopic MVP 版."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException as FastAPIHTTPException

from app.api.v1.one_topic import router as one_topic_router
from app.api.v1.skills import router as skills_router
from app.api.v1.health import router as health_router
from app.api.v1.mcp import router as mcp_router  # Session 36: MCP tools
from app.errors import AppError, app_error_handler, http_exception_handler

app = FastAPI(
    title="TopicPilot-CN OneTopic MVP",
    version="0.2.0",
    description="一题输入 → 关键词拆解 → 三线检索 → 可行性判断 → 开题建议 → 低门槛审核",
)

# CORS: 允许 apps/web dev server (18182) 调后端 (18181)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:18182",
        "http://localhost:18182",
        "http://127.0.0.1:18181",
        "http://localhost:18181",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session 18: 统一错误处理
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(FastAPIHTTPException, http_exception_handler)

app.include_router(one_topic_router)
app.include_router(skills_router)
app.include_router(health_router, prefix="/api/v1")
app.include_router(mcp_router)  # Session 36: MCP tools


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "one_topic_mvp", "session": "18"}
