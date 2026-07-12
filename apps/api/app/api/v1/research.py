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
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from apps.api.app.services.run_state import atomic_write_json

logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "tmp_re13_eval"

_CASE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


def _validate_case_id(case_id: str) -> str:
    """Validate case_id: must be a safe slug or server-generated UUID.

    Rejects path traversal, hidden files, overlength, and special chars.
    """
    if not case_id or len(case_id) > 64:
        raise HTTPException(400, "case_id must be 1-64 characters")
    if not _CASE_ID_PATTERN.match(case_id):
        raise HTTPException(400, "case_id contains invalid characters")
    resolved = (OUT_DIR / case_id).resolve()
    if not str(resolved).startswith(str(OUT_DIR.resolve())):
        raise HTTPException(400, "case_id path traversal detected")
    return case_id

_RUN_STATUS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()
_USER_PAPERS: dict[str, list[dict[str, Any]]] = {}

router = APIRouter()


# ---------------------------------------------------------------------------
# Health / providers
# ---------------------------------------------------------------------------

_PROVIDER_CONFIG = [
    {"key": "deepseek", "label": "DeepSeek", "type": "llm"},
    {"key": "openalex", "label": "OpenAlex", "type": "search"},
    {"key": "crossref", "label": "Crossref", "type": "search"},
    {"key": "arxiv", "label": "arXiv", "type": "search"},
    {"key": "github", "label": "GitHub", "type": "search"},
    {"key": "semantic_scholar", "label": "S2 API", "type": "search"},
]


@router.get("/health/providers")
async def health_providers() -> dict[str, Any]:
    """Check connectivity to all 6 providers (LLM + search adapters)."""
    import httpx

    async def _check_one(prov: dict[str, Any]) -> dict[str, Any]:
        key = prov["key"]
        t0 = time.time()
        try:
            if key == "deepseek":
                api_key = os.environ.get("DEEPSEEK_API_KEY", "")
                ok = bool(api_key)
                latency = 0
                detail = "API key set" if ok else "API key missing"
            else:
                urls = {
                    "openalex": "https://api.openalex.org/works?per_page=1",
                    "crossref": "https://api.crossref.org/works?rows=1",
                    "arxiv": "https://export.arxiv.org/api/query?search_query=all:test&max_results=1",
                    "github": "https://api.github.com/rate_limit",
                    "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1",
                }
                # Use httpx with no_proxy to avoid local proxy issues
                async with httpx.AsyncClient(timeout=2.0, proxy=None, verify=False, follow_redirects=True) as client:
                    resp = await client.get(urls[key])
                    ok = resp.status_code < 500
                    latency = round(time.time() - t0, 2)
                    detail = f"HTTP {resp.status_code}"
        except Exception as exc:
            ok = False
            latency = round(time.time() - t0, 2)
            detail = f"{type(exc).__name__}: {str(exc)[:60]}"
        return {
            "key": key, "label": prov["label"], "type": prov["type"],
            "ok": ok, "latency_s": latency, "detail": detail,
        }

    tasks = [_check_one(p) for p in _PROVIDER_CONFIG]
    results = await asyncio.gather(*tasks)
    n_ok = sum(1 for r in results if r["ok"])
    return {"providers": results, "n_ok": n_ok, "n_total": len(results)}


def _case_dir(case_id: str) -> Path:
    return OUT_DIR / case_id


# ---------------------------------------------------------------------------
# List cases
# ---------------------------------------------------------------------------


def _list_cases_impl() -> dict[str, Any]:
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


@router.get("/")
def list_cases() -> dict[str, Any]:
    return _list_cases_impl()


# ---------------------------------------------------------------------------
# Submit a run (background)
# ---------------------------------------------------------------------------


def _run_case_sync(case_id: str, topic: str, extra: dict[str, Any]) -> None:
    """Synchronous wrapper for the research graph, executed in a thread."""
    t0 = time.time()
    cd = _case_dir(case_id)
    cd.mkdir(parents=True, exist_ok=True)

    # Re3.9.2: pre-create trace.json so SSE polling detects file immediately
    trace_path = cd / "trace.json"
    trace_path.write_text("[]", encoding="utf-8")

    all_trace_events: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}

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
        # Re3.1: inject user-uploaded papers
        user_papers = _USER_PAPERS.pop(case_id, None)
        if user_papers:
            state_in["user_papers"] = user_papers
        g = rg.build_graph()

        # Re3.9.2: stream() instead of invoke() — each node yields a patch
        for chunk in g.stream(
            state_in,
            config={
                "configurable": {"thread_id": case_id},
                "recursion_limit": 100,
            },
            stream_mode="updates",
        ):
            for node_name, patch in chunk.items():
                if not isinstance(patch, dict):
                    continue

                # Collect trace_events (each node returns its own new events)
                node_traces = patch.get("trace_events") or []
                for t in node_traces:
                    all_trace_events.append(t)

                # Real-time write trace.json so SSE polling can pick it up
                trace_path.write_text(
                    json.dumps(all_trace_events, ensure_ascii=False,
                               indent=2, default=str),
                    encoding="utf-8",
                )

                # Merge patch into final_state
                final_state.update(patch)

                # Write partial state for SSE streaming (papers, repos, datasets, verified_papers)
                partial_path = cd / "state_partial.json"
                try:
                    _partial = {
                        "paper_candidates": final_state.get("paper_candidates") or [],
                        "repo_candidates": final_state.get("repo_candidates") or [],
                        "verified_papers": final_state.get("verified_papers") or [],
                        "weak_papers": final_state.get("weak_papers") or [],
                        "dataset_candidates": final_state.get("dataset_candidates") or [],
                        "search_steps": final_state.get("search_steps") or [],
                        "last_update": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    partial_path.write_text(
                        json.dumps(_partial, ensure_ascii=False, default=str),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

                # Re3.9.2: update current_node for SSE node_current event
                with _LOCK:
                    _RUN_STATUS[case_id] = {
                        **_RUN_STATUS.get(case_id, {"status": "running"}),
                        "status": "running",
                        "current_node": node_name,
                        "n_trace_events": len(all_trace_events),
                    }

        elapsed = round(time.time() - t0, 2)
        final_state["elapsed_s"] = elapsed
        final_state["trace_events"] = all_trace_events

        # Final writes — atomic for crash safety
        atomic_write_json(cd / "state.json", final_state)
        atomic_write_json(cd / "trace.json", all_trace_events)
        atomic_write_json(cd / "evidence_graph.json",
                          final_state.get("evidence_graph") or {})
        with _LOCK:
            _RUN_STATUS[case_id] = {
                "status": "done",
                "elapsed_s": elapsed,
                "n_papers": len(final_state.get("verified_papers") or []),
                "n_packages": len(final_state.get("work_packages") or []),
                "n_nodes": len(all_trace_events),
            }
    except Exception as exc:  # noqa: BLE001
        # Preserve partial trace on failure
        trace_path.write_text(
            json.dumps(all_trace_events, ensure_ascii=False,
                       indent=2, default=str),
            encoding="utf-8",
        )
        with _LOCK:
            _RUN_STATUS[case_id] = {
                "status": "error",
                "error": type(exc).__name__,
                "message": str(exc)[:500],
            }


def _submit_topic_impl(topic: str, case_id: str | None = None) -> dict[str, Any]:
    """Submit a topic for background research graph execution."""
    if not case_id:
        case_id = uuid.uuid4().hex[:12]
    else:
        case_id = _validate_case_id(case_id)
    if not topic:
        raise HTTPException(400, "topic is required")

    with _LOCK:
        prev = _RUN_STATUS.get(case_id, {}).get("status")
        if prev == "running":
            return {"case_id": case_id, "status": "running", "message": "already running"}
        _RUN_STATUS[case_id] = {"status": "running", "started_at": time.time(), "topic": topic}

    import threading
    thread = threading.Thread(
        target=_run_case_sync,
        args=(case_id, topic, {"topic_zh": ""}),
        daemon=True,
    )
    thread.start()
    return {"case_id": case_id, "status": "running"}


@router.post("/")
def submit_case(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Submit a topic for background research graph execution."""
    case_id = (payload.get("case_id") or "").strip()
    topic = (payload.get("topic") or "").strip()
    if not case_id:
        case_id = uuid.uuid4().hex[:12]
    else:
        case_id = _validate_case_id(case_id)
    if not topic:
        raise HTTPException(400, "topic is required")

    with _LOCK:
        prev = _RUN_STATUS.get(case_id, {}).get("status")
        if prev == "running":
            return {"case_id": case_id, "status": "running", "message": "already running"}
        _RUN_STATUS[case_id] = {"status": "running", "started_at": time.time(), "topic": topic}

    background_tasks.add_task(_run_case_sync, case_id, topic,
                             {k: v for k, v in payload.items()
                              if k not in ("case_id", "topic")})
    return {"case_id": case_id, "status": "running"}


# ---------------------------------------------------------------------------
# Upload user paper (Re3.1)
# ---------------------------------------------------------------------------

async def _enrich_paper(payload: dict[str, Any]) -> dict[str, Any]:
    """Enrich paper metadata from Crossref/arXiv if DOI/arXiv ID provided."""
    import httpx

    title = (payload.get("title") or "").strip()
    doi = (payload.get("doi") or "").strip()
    arxiv_id = (payload.get("arxiv_id") or "").strip()
    url = (payload.get("url") or "").strip()
    role = (payload.get("role") or "baseline").strip()

    paper: dict[str, Any] = {
        "title": title,
        "doi": doi or None,
        "arxiv_id": arxiv_id or None,
        "url": url,
        "abstract": "",
        "authors": [],
        "year": None,
        "role": role,
    }

    # Try Crossref enrichment if DOI is provided
    if doi:
        try:
            async with httpx.AsyncClient(timeout=10.0, proxy=None, verify=False, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://api.crossref.org/works/{doi}",
                    headers={"User-Agent": "PaperAgent/1.0 (mailto:[email protected])"},
                )
                if resp.status_code == 200:
                    item = resp.json().get("message", {})
                    raw_titles = item.get("title") or []
                    if raw_titles and not title:
                        paper["title"] = str(raw_titles[0])
                    abstract = item.get("abstract")
                    if abstract:
                        paper["abstract"] = abstract[:800]
                    authors = item.get("author") or []
                    paper["authors"] = [
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in authors if isinstance(a, dict)
                    ]
                    issued = item.get("issued") or {}
                    parts = issued.get("date-parts") if isinstance(issued, dict) else None
                    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                        y = parts[0][0]
                        if isinstance(y, int):
                            paper["year"] = y
                    if not url:
                        res = item.get("resource") or {}
                        primary = res.get("primary") if isinstance(res, dict) else None
                        if isinstance(primary, dict):
                            paper["url"] = primary.get("URL", "")
        except Exception:
            pass

    # Try arXiv enrichment if arXiv ID is provided
    if arxiv_id:
        try:
            async with httpx.AsyncClient(timeout=10.0, proxy=None, verify=False, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://export.arxiv.org/api/query?id_list={arxiv_id}",
                )
                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text)
                    ns = "{http://www.w3.org/2005/Atom}"
                    entry = root.find(f"{ns}entry")
                    if entry is not None:
                        t_elem = entry.find(f"{ns}title")
                        if t_elem is not None and not title:
                            paper["title"] = "".join(t_elem.itertext()).strip()
                        s_elem = entry.find(f"{ns}summary")
                        if s_elem is not None:
                            paper["abstract"] = "".join(s_elem.itertext()).strip()[:800]
                        if not url:
                            id_elem = entry.find(f"{ns}id")
                            if id_elem is not None:
                                paper["url"] = "".join(id_elem.itertext()).strip()
        except Exception:
            pass

    if not paper["url"] and arxiv_id:
        paper["url"] = f"https://arxiv.org/abs/{arxiv_id}"
    if not paper["url"] and doi:
        paper["url"] = f"https://doi.org/{doi}"

    return paper


@router.post("/{case_id}/papers")
async def upload_paper(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    """Upload a user-known paper for a case.

    Re8.0: the paper is enriched from Crossref/arXiv if DOI/arXiv ID is
    provided, then staged as a ``candidate_seed``. It is NO LONGER
    auto-accepted into ``verified_papers`` — the ``seed_resolver_node``
    audits authenticity (Crossref/arXiv match) before any promotion to
    evidence. This closes the "fabricated DOI auto-accepts" loophole.
    """
    title = (payload.get("title") or "").strip()
    doi = (payload.get("doi") or "").strip()
    arxiv_id = (payload.get("arxiv_id") or "").strip()
    (payload.get("url") or "").strip()

    if not title and not doi and not arxiv_id:
        raise HTTPException(400, "at least one of title, doi, arxiv_id is required")

    # Enrich metadata
    enriched = await _enrich_paper(payload)

    # Store for later injection when the case runs
    with _LOCK:
        if case_id not in _USER_PAPERS:
            _USER_PAPERS[case_id] = []
        _USER_PAPERS[case_id].append(enriched)

    # Re8.0: If the case already has a state.json, append as candidate_seed.
    # The seed_resolver_node audits authenticity before any promotion to
    # verified_papers / seed_papers. We deliberately do NOT touch
    # verified_papers here — that was the fabricated-DOI loophole.
    state_path = _case_dir(case_id) / "state.json"
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8"))
            cs = st.get("candidate_seeds") or []
            cs.append({
                "seed_id": f"user-seed-{len(cs)}",
                "title": enriched["title"],
                "doi": enriched.get("doi"),
                "arxiv_id": enriched.get("arxiv_id"),
                "url": enriched["url"],
                "authors": enriched.get("authors", []),
                "year": enriched.get("year"),
                "abstract": enriched.get("abstract", ""),
                "role": enriched.get("role", "unknown"),
                "raw_input": enriched,
            })
            st["candidate_seeds"] = cs
            # Force entry_mode to seeded_research so seed_resolver runs
            if st.get("entry_mode", "topic_only") == "topic_only":
                st["entry_mode"] = "seeded_research"
            state_path.write_text(
                json.dumps(st, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("failed to append user paper to state.json: %s", exc)

    return {
        "case_id": case_id,
        "paper": enriched,
        "stored": True,
        "message": "paper staged as candidate_seed; seed_resolver will audit before promotion",
    }


@router.get("/{case_id}/papers")
def list_user_papers(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    """List user-uploaded papers for a case.

    Re8.0: papers are staged as ``candidate_seeds`` and, after the
    ``seed_resolver_node`` runs, audited cards appear in ``seed_cards``.
    We surface both so the caller can see audit status.
    """
    with _LOCK:
        papers = list(_USER_PAPERS.get(case_id, []))
    # Re8.0: read from candidate_seeds (pre-audit) + seed_cards (post-audit)
    state_path = _case_dir(case_id) / "state.json"
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8"))
            for p in st.get("candidate_seeds") or []:
                if p not in papers:
                    papers.append(p)
            for card in st.get("seed_cards") or []:
                # seed_cards are the audited form; expose a paper-like view
                papers.append({
                    "title": card.get("resolved_title") or card.get("raw_input", {}).get("title", ""),
                    "doi": card.get("doi"),
                    "arxiv_id": card.get("arxiv_id"),
                    "url": card.get("canonical_url") or card.get("raw_input", {}).get("url", ""),
                    "authors": card.get("authors", []),
                    "year": card.get("year"),
                    "abstract": card.get("raw_input", {}).get("abstract", ""),
                    "role": card.get("role", "unknown"),
                    "existence_status": card.get("existence_status", "unknown"),
                    "seed_id": card.get("seed_id"),
                    "audited": True,
                })
        except Exception:
            pass
    return {"case_id": case_id, "papers": papers, "n": len(papers)}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def _get_status_impl(case_id: str) -> dict[str, Any]:
    with _LOCK:
        st = dict(_RUN_STATUS.get(case_id, {}))
    cd = _case_dir(case_id)
    st["has_state_json"] = (cd / "state.json").exists()
    st["has_trace_json"] = (cd / "trace.json").exists()
    st["has_evidence_graph_json"] = (cd / "evidence_graph.json").exists()
    if "status" not in st:
        st["status"] = "unknown"
    return st


@router.get("/{case_id}/status")
def case_status(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    return _get_status_impl(case_id)


# ---------------------------------------------------------------------------
# State result
# ---------------------------------------------------------------------------


@router.get("/{case_id}/state")
def case_state(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
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
    case_id = _validate_case_id(case_id)
    """Return the node trace_events list."""
    p = _case_dir(case_id) / "trace.json"
    if not p.exists():
        raise HTTPException(404, f"trace not found for case {case_id!r}")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Timeline (Re3.5)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/timeline")
def case_timeline(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    """Return trace events with progressive state counts for timeline debugger."""
    cd = _case_dir(case_id)
    trace_path = cd / "trace.json"
    state_path = cd / "state.json"
    if not trace_path.exists():
        raise HTTPException(404, f"trace not found for case {case_id!r}")

    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    progressive = []
    n_papers = n_repos = n_datasets = n_baseline = 0

    for ev in trace:
        node = ev.get("node", "")
        out = ev.get("output_summary", {})
        if isinstance(out, dict):
            if "n_paper_candidates" in out:
                n_papers = out["n_paper_candidates"]
            if "n_repo_candidates" in out:
                n_repos = out.get("n_repo_candidates", n_repos)
            if "n_dataset" in out:
                n_datasets = out["n_dataset"]
            if "n_baseline" in out:
                n_baseline = out["n_baseline"]
            if "n_verified" in out:
                n_papers = out["n_verified"]
        if node == "verify" and state.get("verified_papers"):
            n_papers = len(state["verified_papers"])
        if node == "baseline_classifier" and state.get("baseline_candidates"):
            n_baseline = len(state["baseline_candidates"])

        progressive.append({
            "node": node,
            "elapsed_s": ev.get("elapsed_s", 0),
            "cumulative": {
                "papers": n_papers,
                "repos": n_repos,
                "datasets": n_datasets,
                "baseline": n_baseline,
            },
        })

    return {
        "trace": trace,
        "progressive": progressive,
        "total_elapsed_s": round(sum(e.get("elapsed_s", 0) for e in trace), 2),
        "n_events": len(trace),
    }


# ---------------------------------------------------------------------------
# Evidence graph
# ---------------------------------------------------------------------------


@router.get("/{case_id}/evidence-graph")
def case_evidence_graph(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
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


@router.get("/graph-topology")
def graph_topology() -> dict[str, Any]:
    """Return static graph topology for visualization (all cases share same structure)."""
    return {
        "nodes": [
            {"id": "intake", "label": "intake", "x": 120, "y": 30, "group": "input"},
            {"id": "topic_parser", "label": "parser", "x": 120, "y": 80, "group": "parse"},
            {"id": "search_planner", "label": "planner", "x": 120, "y": 130, "group": "search"},
            {"id": "search_agent", "label": "search", "x": 120, "y": 180, "group": "search"},
            {"id": "quality_filter", "label": "filter", "x": 120, "y": 230, "group": "filter"},
            {"id": "verify", "label": "verify", "x": 120, "y": 280, "group": "verify"},
            {"id": "quality_gate", "label": "gate", "x": 120, "y": 330, "group": "verify"},
            {"id": "targeted_repair", "label": "repair", "x": 250, "y": 280, "group": "repair"},
            {"id": "citation_expander", "label": "citation", "x": 250, "y": 330, "group": "expand"},
            {"id": "dataset_repo_extractor", "label": "dataset", "x": 120, "y": 380, "group": "extract"},
            {"id": "evidence_graph_builder", "label": "graph", "x": 120, "y": 430, "group": "audit"},
            {"id": "baseline_classifier", "label": "baseline", "x": 120, "y": 480, "group": "audit"},
            {"id": "feasibility_assessor", "label": "feasibility", "x": 120, "y": 530, "group": "assess"},
            {"id": "human_gate_search", "label": "Gate", "x": 120, "y": 580, "group": "gate"},
            {"id": "work_package", "label": "work_pkg", "x": 120, "y": 630, "group": "analyze"},
            {"id": "innovation_extractor", "label": "innovation", "x": 70, "y": 680, "group": "analyze"},
            {"id": "sota_matcher", "label": "sota", "x": 170, "y": 680, "group": "analyze"},
            {"id": "narrative_builder", "label": "narrative", "x": 120, "y": 730, "group": "analyze"},
            {"id": "low_bar_review", "label": "low_bar", "x": 120, "y": 780, "group": "review"},
            {"id": "optimization_advisor", "label": "optimize", "x": 120, "y": 830, "group": "review"},
            {"id": "devils_advocate", "label": "devils", "x": 120, "y": 880, "group": "review"},
            {"id": "human_gate", "label": "gate2", "x": 120, "y": 930, "group": "gate"},
            {"id": "final_recommendation", "label": "final", "x": 120, "y": 980, "group": "output"},
        ],
        "edges": [
            {"from": "intake", "to": "topic_parser"},
            {"from": "topic_parser", "to": "search_planner"},
            {"from": "search_planner", "to": "search_agent"},
            {"from": "search_agent", "to": "quality_filter"},
            {"from": "quality_filter", "to": "verify"},
            {"from": "verify", "to": "quality_gate"},
            {"from": "quality_gate", "to": "targeted_repair", "dashed": True},
            {"from": "quality_gate", "to": "citation_expander", "dashed": True},
            {"from": "quality_gate", "to": "dataset_repo_extractor", "dashed": True},
            {"from": "targeted_repair", "to": "search_agent", "dashed": True, "label": "repair"},
            {"from": "citation_expander", "to": "verify", "dashed": True, "label": "expand"},
            {"from": "dataset_repo_extractor", "to": "evidence_graph_builder"},
            {"from": "evidence_graph_builder", "to": "baseline_classifier"},
            {"from": "baseline_classifier", "to": "feasibility_assessor"},
            {"from": "feasibility_assessor", "to": "human_gate_search", "dashed": True},
            {"from": "human_gate_search", "to": "work_package"},
            {"from": "work_package", "to": "innovation_extractor"},
            {"from": "work_package", "to": "sota_matcher"},
            {"from": "innovation_extractor", "to": "narrative_builder"},
            {"from": "sota_matcher", "to": "narrative_builder"},
            {"from": "narrative_builder", "to": "low_bar_review"},
            {"from": "low_bar_review", "to": "optimization_advisor", "dashed": True},
            {"from": "optimization_advisor", "to": "devils_advocate"},
            {"from": "devils_advocate", "to": "narrative_builder", "dashed": True, "label": "revision"},
            {"from": "devils_advocate", "to": "human_gate", "dashed": True},
            {"from": "human_gate", "to": "final_recommendation"},
        ],
    }


@router.get("/{case_id}/stream")
async def case_stream(case_id: str):
    case_id = _validate_case_id(case_id)
    """SSE stream of node progress for a running or completed case."""

    sent_events: int = 0
    last_trace_count: int = 0
    last_current_node: str = ""
    last_partial_mtime: float = 0.0  # Re3.9.3: track partial state changes
    poll_interval = 0.3  # Re3.9.2: faster polling
    max_wait = 600  # 10 min timeout
    waited = 0.0

    async def event_generator():
        nonlocal sent_events, last_trace_count, waited, last_current_node, last_partial_mtime

        # Send search_started immediately if case is running
        with _LOCK:
            status = _RUN_STATUS.get(case_id, {}).get("status", "unknown")
            topic = _RUN_STATUS.get(case_id, {}).get("topic", "")

        yield _sse_event("search_started", {"case_id": case_id, "status": status, "topic": topic})

        while waited < max_wait:
            with _LOCK:
                status = _RUN_STATUS.get(case_id, {}).get("status", "unknown")

            # Re3.9.2: push node_current when the running node changes
            current_node = _RUN_STATUS.get(case_id, {}).get("current_node", "")
            if current_node and current_node != last_current_node:
                yield _sse_event("node_current", {"node": current_node})
                last_current_node = current_node

            # Re3.9.3: push papers_update when state_partial.json changes
            partial_path = _case_dir(case_id) / "state_partial.json"
            if partial_path.exists():
                try:
                    partial_mtime = partial_path.stat().st_mtime
                    if partial_mtime != last_partial_mtime:
                        last_partial_mtime = partial_mtime
                        partial = json.loads(partial_path.read_text(encoding="utf-8"))
                        papers = partial.get("paper_candidates") or []
                        repos = partial.get("repo_candidates") or []
                        yield _sse_event("papers_update", {
                            "papers": [{"title": (p.get("title") or "")[:120],
                                        "source": p.get("source", ""),
                                        "url": p.get("url", ""),
                                        "year": p.get("year"),
                                        "authors": (p.get("authors") or [])[:3],
                                        "abstract": (p.get("abstract") or "")[:200],
                                        "verdict": p.get("verdict"),
                                        "relation_to_topic": p.get("relation_to_topic", ""),
                                        "relevance_score": p.get("relevance_score")}
                                       for p in papers[:50]],
                            "n_papers": len(papers),
                            "n_repos": len(repos),
                            "repos": [{"full_name": r.get("full_name", r.get("url", "")),
                                        "url": r.get("url", ""),
                                        "stars": r.get("stars"),
                                        "description": (r.get("description") or "")[:100],
                                        "language": r.get("language", "")}
                                       for r in repos[:20]],
                            "search_step": (partial.get("search_steps") or [{}])[-1].get("step", 0),
                        })
                except Exception:
                    pass

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
                    per_adapter = output_summary.get("per_adapter", {})
                    failed_adapters = output_summary.get("failed_adapters", [])
                    skipped_adapters = output_summary.get("skipped_adapters", [])
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
                    # Re2.4: adapter_status event with per-adapter detail
                    yield _sse_event("adapter_status", {
                        "per_adapter": per_adapter,
                        "failed_adapters": failed_adapters,
                        "skipped_adapters": skipped_adapters,
                        "total_raw": total_raw,
                    })

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
                    # Re2.4: candidate_count after verify
                    yield _sse_event("candidate_count", {
                        "papers": n_accept + n_weak,
                        "accept": n_accept,
                        "weak": n_weak,
                        "reject": n_reject,
                    })
                    # Send verified papers with verdicts for real-time display
                    partial_path = _case_dir(case_id) / "state_partial.json"
                    verified_papers: list = []
                    weak_papers: list = []
                    if partial_path.exists():
                        try:
                            partial = json.loads(partial_path.read_text(encoding="utf-8"))
                            verified_papers = partial.get("verified_papers") or []
                            weak_papers = partial.get("weak_papers") or []
                        except Exception:
                            pass
                    if verified_papers or weak_papers:
                        all_verified = verified_papers + weak_papers
                        yield _sse_event("papers_verified", {
                            "papers": [{"title": (p.get("title") or "")[:120],
                                        "source": p.get("source", ""),
                                        "url": p.get("url", ""),
                                        "year": p.get("year"),
                                        "verdict": p.get("verdict", "accept"),
                                        "relation_to_topic": p.get("relation_to_topic", ""),
                                        "relevance_score": p.get("relevance_score"),
                                        "abstract": (p.get("abstract") or "")[:200]}
                                       for p in all_verified[:50]],
                            "n_verified": len(verified_papers),
                            "n_weak": len(weak_papers),
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
                    # Re2.4: candidate_count after expansion
                    yield _sse_event("candidate_count", {
                        "expanded": output_summary.get("n_expanded", 0),
                        "surveys": output_summary.get("n_surveys", 0),
                        "repos": output_summary.get("n_repos", 0),
                        "seeds": len(seeds),
                    })

                elif node == "dataset_repo_extractor":
                    # Send repos and datasets for real-time display
                    partial_path = _case_dir(case_id) / "state_partial.json"
                    repos_data: list = []
                    datasets_data: list = []
                    if partial_path.exists():
                        try:
                            partial = json.loads(partial_path.read_text(encoding="utf-8"))
                            repos_data = partial.get("repo_candidates") or []
                            datasets_data = partial.get("dataset_candidates") or []
                        except Exception:
                            pass
                    yield _sse_event("repos_update", {
                        "repos": [{"full_name": r.get("full_name", r.get("url", "")),
                                    "url": r.get("url", ""),
                                    "stars": r.get("stars"),
                                    "description": (r.get("description") or "")[:100],
                                    "language": r.get("language", "")}
                                   for r in repos_data[:30]],
                        "n_repos": len(repos_data),
                    })
                    yield _sse_event("datasets_update", {
                        "datasets": [{"name": d.get("name", ""),
                                       "url": d.get("url", ""),
                                       "source": d.get("source", ""),
                                       "description": (d.get("description") or "")[:100]}
                                      for d in datasets_data[:30]],
                        "n_datasets": len(datasets_data),
                    })
                    yield _sse_event("candidate_count", {
                        "repos": len(repos_data),
                        "datasets": len(datasets_data),
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
    case_id = _validate_case_id(case_id)
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


def _get_evidence_graph_impl(case_id: str) -> dict[str, Any]:
    p = _case_dir(case_id) / "evidence_graph.json"
    if not p.exists():
        return {"nodes": [], "edges": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _list_user_papers_impl(case_id: str) -> dict[str, Any]:
    """List user-uploaded papers (ACP version). Re8.0: reads from
    candidate_seeds + seed_cards, same logic as HTTP list_user_papers."""
    with _LOCK:
        papers = list(_USER_PAPERS.get(case_id, []))
    state_path = _case_dir(case_id) / "state.json"
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8"))
            for p in st.get("candidate_seeds") or []:
                if p not in papers:
                    papers.append(p)
            for card in st.get("seed_cards") or []:
                papers.append({
                    "title": card.get("resolved_title") or card.get("raw_input", {}).get("title", ""),
                    "doi": card.get("doi"),
                    "arxiv_id": card.get("arxiv_id"),
                    "url": card.get("canonical_url") or card.get("raw_input", {}).get("url", ""),
                    "authors": card.get("authors", []),
                    "year": card.get("year"),
                    "abstract": card.get("raw_input", {}).get("abstract", ""),
                    "role": card.get("role", "unknown"),
                    "existence_status": card.get("existence_status", "unknown"),
                    "seed_id": card.get("seed_id"),
                    "audited": True,
                })
        except Exception:
            pass
    return {"case_id": case_id, "papers": papers, "n": len(papers)}


def _get_work_packages_impl(case_id: str) -> dict[str, Any]:
    state = _load_state(case_id)
    packages = state.get("work_packages") or []
    from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag
    dag = build_dag(packages)
    return {"case_id": case_id, "work_packages": packages, "dag": dag, "n": len(packages)}


def _get_feasibility_impl(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("feasibility_report", {})


def _get_review_impl(case_id: str) -> dict[str, Any]:
    return _load_state(case_id).get("review_report", {})


def _get_innovation_impl(case_id: str) -> dict[str, Any]:
    st = _load_state(case_id)
    return {"innovation_points": st.get("innovation_points", []),
            "stitching_plan": st.get("stitching_plan", {})}


def _upload_paper_impl(case_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Upload a user-known paper (synchronous version for ACP).

    Re8.0: staged as candidate_seed — seed_resolver audits before promotion.
    NO LONGER auto-accepts into verified_papers (closes fabricated-DOI loophole).
    """
    title = (params.get("title") or "").strip()
    doi = (params.get("doi") or "").strip()
    arxiv_id = (params.get("arxiv_id") or "").strip()

    if not title and not doi and not arxiv_id:
        raise HTTPException(400, "at least one of title, doi, arxiv_id is required")

    paper: dict[str, Any] = {
        "title": title,
        "doi": doi or None,
        "arxiv_id": arxiv_id or None,
        "url": params.get("url") or "",
        "abstract": "",
        "authors": [],
        "year": None,
        "role": params.get("role") or "baseline",
    }

    with _LOCK:
        if case_id not in _USER_PAPERS:
            _USER_PAPERS[case_id] = []
        _USER_PAPERS[case_id].append(paper)

    # Re8.0: stage as candidate_seed, NOT verified_papers
    state_path = _case_dir(case_id) / "state.json"
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8"))
            cs = st.get("candidate_seeds") or []
            cs.append({
                "seed_id": f"user-seed-{len(cs)}",
                "title": paper["title"],
                "doi": paper.get("doi"),
                "arxiv_id": paper.get("arxiv_id"),
                "url": paper["url"],
                "authors": paper.get("authors", []),
                "year": paper.get("year"),
                "abstract": paper.get("abstract", ""),
                "role": paper.get("role", "unknown"),
                "raw_input": paper,
            })
            st["candidate_seeds"] = cs
            if st.get("entry_mode", "topic_only") == "topic_only":
                st["entry_mode"] = "seeded_research"
            atomic_write_json(state_path, st)
        except Exception as exc:
            logger.warning("failed to append user paper to state.json: %s", exc)

    return {
        "case_id": case_id,
        "paper": paper,
        "stored": True,
        "message": "paper staged as candidate_seed; seed_resolver will audit before promotion",
    }


@router.get("/{case_id}/feasibility")
def case_feasibility(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    return _load_state(case_id).get("feasibility_report", {})


@router.get("/{case_id}/innovation")
def case_innovation(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    st = _load_state(case_id)
    return {"innovation_points": st.get("innovation_points", []),
            "stitching_plan": st.get("stitching_plan", {})}


@router.get("/{case_id}/sota")
def case_sota(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    return _load_state(case_id).get("sota_comparison", {})


@router.get("/{case_id}/narrative")
def case_narrative(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    return _load_state(case_id).get("research_narrative", {})


@router.get("/{case_id}/optimization")
def case_optimization(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    return _load_state(case_id).get("optimization_directions", {})


@router.get("/{case_id}/review")
def case_review(case_id: str) -> dict[str, Any]:
    case_id = _validate_case_id(case_id)
    return _load_state(case_id).get("review_report", {})


@router.get("/{case_id}/work-packages")
def get_work_packages(case_id: str) -> dict[str, Any]:
    """Get work packages with dependency DAG."""
    case_id = _validate_case_id(case_id)
    state = _load_state(case_id)
    packages = state.get("work_packages") or []
    from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag
    dag = build_dag(packages)
    return {"case_id": case_id, "work_packages": packages, "dag": dag, "n": len(packages)}
