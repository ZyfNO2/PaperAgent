"""FastAPI 入口 — OneTopic MVP 版."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.one_topic import router as one_topic_router

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

app.include_router(one_topic_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "one_topic_mvp"}
