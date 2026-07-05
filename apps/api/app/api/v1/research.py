"""FastAPI router for Re1.3 research graph results.

Endpoints:
  GET  /api/v1/research/                     list case IDs with results on disk
  POST /api/v1/research/                     submit a topic (background run)
  GET  /api/v1/research/{case_id}/status     check run status
  GET  /api/v1/research/{case_id}/state      final ResearchState JSON
  GET  /api/v1/research/{case_id}/trace       per-node trace_events list
  GET  /api/v1/research/{case_id}/evidence-graph  evidence_graph JSON
  GET  /api/v1/research/{case_id}/stream      SSE stream of node progress
  GET  /api/v1/research/{case_id}/expanded    citation expansion results

Results are read/written under ``tmp_re13_eval/<case_id>/``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "tmp_re13_eval"

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


# ---------------------------------------------------------------------------
# SSE Stream
# ---------------------------------------------------------------------------


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.get("/{case_id}/stream")
async def case_stream(case_id: str):
    """SSE stream of node progress for a running or completed case."""
    import collections

    sent_events: int = 0
    last_trace_count: int = 0
    poll_interval = 0.5
    max_wait = 600  # 10 min timeout
    waited = 0.0

    async def event_generator():
        nonlocal sent_events, last_trace_count, waited

        # Send search_started immediately if case is running
        with _LOCK:
            status = _RUN_STATUS.get(case_id, {}).get("status", "unknown")

        yield _sse_event("search_started", {"case_id": case_id, "status": status})

        while waited < max_wait:
            with _LOCK:
                status = _RUN_STATUS.get(case_id, {}).get("status", "unknown")

            # Check for new trace events
            trace_path = _case_dir(case_id) / "trace.json"
            if trace_path.exists():
                try:
                    traces = json.loads(trace_path.read_text(encoding="utf-8"))
                except Exception:
                    traces = []
            else:
                traces = []

            # Send new trace events
            new_traces = traces[last_trace_count:]
            for t in new_traces:
                node = t.get("node", "")
                output_summary = t.get("output_summary", {})
                input_summary = t.get("input_summary", {})
                tool_calls = t.get("tool_calls", [])

                if node == "retrieve" or node == "paper_retriever":
                    # Parse adapter results from tool_calls
                    for tc in tool_calls:
                        tool = tc.get("tool", "")
                        n = tc.get("n", 0)
                        if tool and n:
                            yield _sse_event("adapter_result", {
                                "adapter": tool,
                                "count": n,
                            })
                    total_raw = sum(tc.get("n", 0) for tc in tool_calls if isinstance(tc.get("n"), int))
                    yield _sse_event("search_completed", {"total_raw": total_raw})

                elif node == "quality_filter":
                    yield _sse_event("filter_result", {
                        "kept": output_summary.get("kept", 0),
                        "dropped": output_summary.get("dropped", 0),
                        "pre_filter_keep": output_summary.get("pre_filter_keep", 0),
                        "pre_filter_drop": output_summary.get("pre_filter_drop", 0),
                        "llm_judged": output_summary.get("llm_judged", 0),
                    })

                elif node == "verify":
                    round_n = input_summary.get("round", 1)
                    n_accept = output_summary.get("n_accept", 0)
                    n_weak = output_summary.get("n_weak_reject", output_summary.get("n_reject_or_weak", 0))
                    n_reject = output_summary.get("n_reject", 0)
                    yield _sse_event("verify_completed", {
                        "accepted": n_accept,
                        "weak_reject": n_weak,
                        "rejected": n_reject,
                        "round": round_n,
                    })

                elif node == "citation_expander":
                    # Read state.json for seed details
                    state_path = _case_dir(case_id) / "state.json"
                    seeds = []
                    if state_path.exists():
                        try:
                            st_tmp = json.loads(state_path.read_text(encoding="utf-8"))
                            seeds = st_tmp.get("seed_papers") or []
                        except Exception:
                            pass
                    yield _sse_event("expansion_started", {
                        "n_seeds": len(seeds),
                        "seed_titles": [s.get("title", "")[:80] for s in seeds],
                        "seed_scores": [s.get("relevance_score", 0) for s in seeds],
                    })
                    yield _sse_event("expansion_completed", {
                        "total_expanded": output_summary.get("n_expanded", 0),
                        "n_surveys": output_summary.get("n_surveys", 0),
                        "n_repos": output_summary.get("n_repos", 0),
                    })

                else:
                    yield _sse_event("node_complete", {
                        "node": node,
                        "output": output_summary,
                        "elapsed_s": t.get("elapsed_s", 0),
                    })

                last_trace_count += 1
                sent_events += 1

            # Check if done
            if status == "done":
                # Send done event with summary stats
                state_path = _case_dir(case_id) / "state.json"
                elapsed = 0
                done_data: dict[str, Any] = {
                    "case_id": case_id,
                    "total_elapsed_s": 0,
                    "total_events": sent_events,
                }
                if state_path.exists():
                    try:
                        st = json.loads(state_path.read_text(encoding="utf-8"))
                        elapsed = st.get("elapsed_s", 0)
                        done_data["total_elapsed_s"] = elapsed
                        done_data["n_verified"] = len(st.get("verified_papers") or [])
                        done_data["n_weak"] = len(st.get("weak_papers") or [])
                        done_data["n_expanded"] = len(st.get("expanded_papers") or [])
                        done_data["n_work_packages"] = len(st.get("work_packages") or [])
                        done_data["n_baseline"] = len(st.get("baseline_candidates") or [])
                    except Exception:
                        pass
                yield _sse_event("done", done_data)
                return

            if status == "error":
                yield _sse_event("error", {
                    "node": "unknown",
                    "message": _RUN_STATUS.get(case_id, {}).get("message", "unknown error"),
                })
                return

            await asyncio.sleep(poll_interval)
            waited += poll_interval

        # Timeout
        yield _sse_event("error", {"node": "timeout", "message": "stream timeout"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Citation expansion results
# ---------------------------------------------------------------------------


@router.get("/{case_id}/expanded")
def case_expanded(case_id: str) -> dict[str, Any]:
    """Return citation expansion results (seeds, expanded papers, surveys, repos)."""
    p = _case_dir(case_id) / "state.json"
    if not p.exists():
        raise HTTPException(404, f"state not found for case {case_id!r}")
    st = json.loads(p.read_text(encoding="utf-8"))
    return {
        "seed_papers": st.get("seed_papers") or [],
        "expanded_papers": st.get("expanded_papers") or [],
        "surveys_found": st.get("surveys_found") or [],
        "repos_found": st.get("repos_found") or [],
        "expansion_trace": [
            t for t in (st.get("trace_events") or [])
            if t.get("node") == "citation_expander"
        ],
    }


# ---------------------------------------------------------------------------
# Re1.4 analysis endpoints
# ---------------------------------------------------------------------------

def _load_state(case_id: str) -> dict[str, Any]:
    p = _case_dir(case_id) / "state.json"
    if not p.exists():
        raise HTTPException(404, f"state not found for case {case_id!r}")
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/{case_id}/feasibility")
def case_feasibility(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("feasibility_report", {})


@router.get("/{case_id}/innovation")
def case_innovation(case_id: str) -> dict[str, Any]:
    st = _load_state(case_id)
    return {"innovation_points": st.get("innovation_points", []),
            "stitching_plan": st.get("stitching_plan", {})}


@router.get("/{case_id}/sota")
def case_sota(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("sota_comparison", {})


@router.get("/{case_id}/narrative")
def case_narrative(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("research_narratives", {})


@router.get("/{case_id}/optimization")
def case_optimization(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("optimization_directions", {})


@router.get("/{case_id}/review")
def case_review(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("review_report", {})
