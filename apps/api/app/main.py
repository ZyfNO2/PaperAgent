"""FastAPI entry point — Re1.4 agent edition."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root and apps/api to sys.path so both `apps.api.app.services...`
# and `app.api.v1.research` imports work when uvicorn is started from any directory
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_API_ROOT = str(Path(__file__).resolve().parent.parent)
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

# Load .env from project root (so bat-launched uvicorn gets API keys)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.research import router as research_v1_router
from apps.api.app.api.v1.acp import router as acp_router
from apps.api.app.api.v1.llm import router as llm_router
from apps.api.app.api.v1.providers import router as providers_router
from apps.api.app.api.v1.jobs import router as jobs_router
from apps.api.app.api.v1.feedback import router as feedback_router

app = FastAPI(
    title="PaperAgent Re4",
    version="0.4.0-dev",
    description="Frontend + citation expansion + quality filter",
)

# Re7.6: Register graph-node contracts at startup so unified_router path
# is active for all nodes that declare a contract_id.
try:
    from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
    register_graph_contracts()
except Exception as _exc:
    import logging
    logging.getLogger(__name__).warning("register_graph_contracts failed: %s", _exc)

_cors_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:18181").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Re1.2/1.3 research graph result endpoints
app.include_router(research_v1_router, prefix="/api/v1/research", tags=["research-v1"])
app.include_router(acp_router)
app.include_router(llm_router)
app.include_router(providers_router)
app.include_router(jobs_router)
app.include_router(feedback_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "re40", "session": "day1"}


# Re1.3: static frontend mount (must be last so it doesn't shadow API routes)
_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
if _WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")

# Re4.2: React frontend build (if dist exists)
_REACT_DIST = Path(__file__).resolve().parent.parent.parent / "web-react" / "dist"
if _REACT_DIST.is_dir():
    app.mount("/react", StaticFiles(directory=str(_REACT_DIST), html=True), name="react")
