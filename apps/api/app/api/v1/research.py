"""FastAPI router for Re1.2 research graph results.

Endpoints:
  GET  /api/v1/research/                     list case IDs with results on disk
  POST /api/v1/research/                     submit a topic (background run)
  GET  /api/v1/research/{case_id}/status     check run status
  GET  /api/v1/research/{case_id}/state      final ResearchState JSON
  GET  /api/v1/research/{case_id}/trace       per-node trace_events list
  GET  /api/v1/research/{case_id}/evidence-graph  evidence_graph JSON

Results are read/written under ``tmp_re12_eval/<case_id>/`` so the CLI runner
and the API share the same artifact directory.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

logger = logging.getLogger(__name__)

# Shared with re12_run.py
OUT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "tmp_re12_eval"

# In-memory status for background runs
_RUN_STATUS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()

router = APIRouter()


def _case_dir(case_id: str) -> Path:
    return OUT_DIR / case_id


# ---------------------------------------------------------------------------
# List cases
# ---------------------------------------------------------------------------


@router.get("/")
def list_cases() -> dict[str, Any]:
    """List case IDs that have at least a state.json on disk."""
    if not OUT_DIR.is_dir():
        return {"cases": []}
    cases: list[dict[str, Any]] = []
    for d in sorted(OUT_DIR.iterdir()):
        if not d.is_dir():
            continue
        sf = d / "state.json"
        if sf.exists():
            stat = sf.stat()
            status = _RUN_STATUS.get(d.name, {}).get("status", "done")
            cases.append({
                "case_id": d.name,
                "file_size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "status": status,
            })
    return {"cases": cases, "n": len(cases)}


# ---------------------------------------------------------------------------
# Submit a run (background)
# ---------------------------------------------------------------------------


def _run_case_sync(case_id: str, topic: str, extra: dict[str, Any]) -> None:
    """Synchronous wrapper for the research graph, executed in a thread."""
    t0 = time.time()
    try:
        from apps.api.app.services.agents.graph import research_graph as rg
        from apps.api.app.services.agents.graph.state import ResearchState

        state_in: ResearchState = {
            "case_id": case_id,
            "topic": topic,
            "user_constraints": extra.get("user_constraints",
                                          {"topic_zh": extra.get("title", "")}),
            "trace_events": [],
            "provider_profile": "fast_json",
            "errors": [],
        }
        g = rg.build_graph()
        out = g.invoke(state_in, config={"configurable": {"thread_id": case_id}})
        elapsed = round(time.time() - t0, 2)
        out["elapsed_s"] = elapsed

        cd = _case_dir(case_id)
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "state.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        (cd / "trace.json").write_text(
            json.dumps(out.get("trace_events") or [], ensure_ascii=False,
                        indent=2, default=str),
            encoding="utf-8",
        )
        (cd / "evidence_graph.json").write_text(
            json.dumps(out.get("evidence_graph") or {}, ensure_ascii=False,
                        indent=2, default=str),
            encoding="utf-8",
        )
        with _LOCK:
            _RUN_STATUS[case_id] = {
                "status": "done",
                "elapsed_s": elapsed,
                "n_papers": len(out.get("verified_papers") or []),
                "n_packages": len(out.get("work_packages") or []),
                "n_nodes": len(out.get("trace_events") or []),
            }
    except Exception as exc:  # noqa: BLE001
        with _LOCK:
            _RUN_STATUS[case_id] = {
                "status": "error",
                "error": type(exc).__name__,
                "message": str(exc)[:500],
            }


@router.post("/")
def submit_case(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Submit a topic for background research graph execution."""
    case_id = (payload.get("case_id") or "").strip()
    topic = (payload.get("topic") or "").strip()
    if not case_id:
        raise HTTPException(400, "case_id is required")
    if not topic:
        raise HTTPException(400, "topic is required")

    with _LOCK:
        prev = _RUN_STATUS.get(case_id, {}).get("status")
        if prev == "running":
            return {"case_id": case_id, "status": "running", "message": "already running"}
        _RUN_STATUS[case_id] = {"status": "running", "started_at": time.time()}

    background_tasks.add_task(_run_case_sync, case_id, topic,
                             {k: v for k, v in payload.items()
                              if k not in ("case_id", "topic")})
    return {"case_id": case_id, "status": "running"}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/{case_id}/status")
def case_status(case_id: str) -> dict[str, Any]:
    with _LOCK:
        st = dict(_RUN_STATUS.get(case_id, {}))
    cd = _case_dir(case_id)
    st["has_state_json"] = (cd / "state.json").exists()
    st["has_trace_json"] = (cd / "trace.json").exists()
    st["has_evidence_graph_json"] = (cd / "evidence_graph.json").exists()
    if "status" not in st:
        st["status"] = "unknown"
    return st


# ---------------------------------------------------------------------------
# State result
# ---------------------------------------------------------------------------


@router.get("/{case_id}/state")
def case_state(case_id: str) -> dict[str, Any]:
    """Return the full final ResearchState."""
    p = _case_dir(case_id) / "state.json"
    if not p.exists():
        raise HTTPException(404, f"state not found for case {case_id!r}")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Trace events
# ---------------------------------------------------------------------------


@router.get("/{case_id}/trace")
def case_trace(case_id: str) -> list[dict[str, Any]]:
    """Return the node trace_events list."""
    p = _case_dir(case_id) / "trace.json"
    if not p.exists():
        raise HTTPException(404, f"trace not found for case {case_id!r}")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Evidence graph
# ---------------------------------------------------------------------------


@router.get("/{case_id}/evidence-graph")
def case_evidence_graph(case_id: str) -> dict[str, Any]:
    """Return the evidence_graph ({nodes, edges}) for front-end consumption."""
    p = _case_dir(case_id) / "evidence_graph.json"
    if not p.exists():
        raise HTTPException(404, f"evidence_graph not found for case {case_id!r}")
    return json.loads(p.read_text(encoding="utf-8"))
