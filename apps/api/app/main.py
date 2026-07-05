"""FastAPI entry point — S66v agent-only edition.

All legcy routers have been moved to `app.Legcy.api_v1/` and are
deliberately NOT mounted. S66v only exposes a minimal health check;
the agent logic is reached through direct script invocation
(`python -m app.services.agents.research_agent <topic>`) and
through the SSR/CLI trace pipeline. To restore legcy routes,
see `Plan/reports/PaperAgent_S66v_报告.md`.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.research import router as research_v1_router

app = FastAPI(
    title="TopicPilot-CN S66v agent",
    version="0.7.0",
    description="Agent-only entry. Legcy routes are quarantined under app.Legcy.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Re1.2 research graph result endpoints
app.include_router(research_v1_router, prefix="/api/v1/research", tags=["research-v1"])


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "s66v_agent", "session": "66v"}


@app.get("/v1/agent/run", tags=["agent"])
def agent_run(topic: str, auto_devils_advocate: bool = True) -> dict:
    """Synchronous convenience endpoint that runs the agent once.

    For full async streaming use `python -m app.services.agents.research_agent`.
    """
    import asyncio
    from app.services.agents.research_agent import run_research_agent, reset_counter
    reset_counter()
    result = asyncio.run(run_research_agent(topic, auto_devils_advocate=auto_devils_advocate))
    return {
        "topic": result.raw_topic,
        "project_id": result.project_id,
        "llm_calls": result.llm_calls,
        "domain_route": result.parsed_topic.get("domain_route"),
        "buckets": result.buckets,
        "raw_tool_sizes": {k: len(v) for k, v in result.raw_tool_results.items()},
        "overall_verdict": result.overall_verdict,
        "fabrication_alerts": result.fabrication_alerts,
    }
