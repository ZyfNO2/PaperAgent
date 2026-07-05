"""FastAPI entry point — Re1.3 agent edition.

Re1.3 changes:
  - Static file mount for apps/web (frontend)
  - Updated title/version
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.research import router as research_v1_router

app = FastAPI(
    title="PaperAgent Re1.3",
    version="1.3.0",
    description="Frontend + citation expansion + quality filter",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Re1.2/1.3 research graph result endpoints
app.include_router(research_v1_router, prefix="/api/v1/research", tags=["research-v1"])


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "re13", "session": "66v"}


# Re1.3: static frontend mount (must be last so it doesn't shadow API routes)
_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
if _WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
