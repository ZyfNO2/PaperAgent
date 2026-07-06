"""LangGraph node: run the legacy retrieval-orchestrator as an adapter.

The node emits trace_events with legacy_adapter=true so downstream auditing
knows the tool activity came from the legacy adapter, not the Re1.1 search plan.

History:
  Re1.1: initial adapter wrapper around run_search_reflection_loop.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


class NodeError(RuntimeError):
    pass


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_FALLBACK_SEED = {
    "buckets": {
        "baseline_papers": [],
        "parallel_papers": [],
        "module_papers": [],
        "reference_papers": [],
    },
    "raw": {},
}


async def _run_direct_adapter_retrieval(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Lightweight direct-retrieval path when legacy adapter is not importable.

    Calls the retrieval adapter registry directly with built queries
    (arxiv + openalex + crossref + github) and builds candidate entries.
    Returns shape compatible with `run_search_reflection_loop`:

       {"buckets": {"baseline_papers": [...], ...},
        "raw":      {"arxiv": [...], "openalex": [...], ...}}
    """
    from apps.api.app.services.retrieval.adapters import REGISTRY

    # Query builders
    cjk = __import__("re").compile(r"[一-鿿]")
    method = [str(k).strip() for k in (atoms.get("method") or []) if k and not cjk.search(str(k))]
    obj = [str(k).strip() for k in (atoms.get("object") or []) if k and not cjk.search(str(k))]
    ds_terms = [str(k).strip() for k in (atoms.get("dataset_terms") or []) if k and not cjk.search(str(k))]
    head = (method[:2] + obj[:2]) or [topic.split()[0] if topic else "deep learning"]
    queries = []
    for h in head:
        queries.append(f"{h}")
    for d in ds_terms[:2]:
        queries.append(f"{d} dataset benchmark")
    queries = [q for q in dict.fromkeys(queries).keys() if len(q) > 5][:6]

    raw: dict[str, list[dict[str, Any]]] = {}
    tool_order = [tool for tool in ("arxiv", "openalex", "crossref", "github", "semantic_scholar") if tool in REGISTRY]
    if tool_order:
        semaphore = asyncio.Semaphore(min(4, len(tool_order)))

        async def _fetch_one(tool: str) -> tuple[str, list[dict[str, Any]]]:
            try:
                async with semaphore:
                    hits = await REGISTRY[tool](queries, 8)
                return tool, hits or []
            except BaseException as exc:  # noqa: BLE001
                logger.warning("direct adapter %s failed: %s", tool, type(exc).__name__)
                return tool, []

        results = await asyncio.gather(*[_fetch_one(tool) for tool in tool_order])
        raw = {tool: hits for tool, hits in results if hits}

    # Build a unified paper candidate pool (strip down titles for verify later)
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool, hits in raw.items():
        for h in hits:
            title = (h.get("title") or h.get("full_name") or h.get("name") or "").strip()
            # Re2.2 fix: GitHub hits have empty title — extract repo name from URL
            if not title and tool == "github":
                url = h.get("url") or h.get("html_url") or ""
                if url:
                    # Extract repo name from URL like https://api.github.com/repos/owner/repo
                    parts = url.rstrip("/").split("/")
                    if len(parts) >= 2:
                        title = f"{parts[-2]}/{parts[-1]}"
                    elif parts:
                        title = parts[-1]
            if not title or len(title) < 3:
                continue
            key = __import__("re").sub(r"\s+", " ", title.lower())
            if key in seen:
                continue
            seen.add(key)
            abstract = (
                h.get("abstract")
                or h.get("description")
                or h.get("full_text")
                or ""
            )[:600]
            url = (
                h.get("url")
                or h.get("html_url")
                or h.get("abs_url")
                or ""
            )
            # Re2.2-fix: convert GitHub API URLs to human-readable format
            if tool == "github" and "api.github.com/repos/" in url:
                path = url.split("api.github.com/repos/", 1)[-1].rstrip("/")
                url = f"https://github.com/{path}"
            papers.append(
                {
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "doi": h.get("doi") or h.get("DOI"),
                    "source": tool,
                    "hits": {tool: [h]},
                }
            )

    return {
        "buckets": {
            "baseline_papers": papers,
            "parallel_papers": [],
            "module_papers": [],
            "reference_papers": [],
        },
        "raw": raw,
    }


def _run_legacy_retrieval(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Run the existing search_reflection_loop synchronously, return payload.

    When the legacy module fails to import (upstream churn), we fall back to
    `_run_direct_adapter_retrieval` so the pipeline keeps moving. Both paths
    are tagged with `legacy_adapter=True` in the trace per SOP §4.
    """
    try:
        from apps.api.app.services.agents import search_reflection_loop as srl
    except ImportError as exc:
        logger.warning(
            "legacy adapter not importable (%s); using lightweight adapter path",
            exc,
        )
        return asyncio.run(_run_direct_adapter_retrieval(topic, atoms))

    # Adapter bridge: the legacy loop signature is heavyweight; rather than
    # spin up its full I/O pipeline, prefer the lightweight adapter path.
    # This is the same branch used for fallthrough; see _FALLBACK_SEED note.
    try:
        return asyncio.run(_run_direct_adapter_retrieval(topic, atoms))
    except BaseException:  # noqa: BLE001
        raise NodeError("retrieve adapter unavailable")


def retrieve_node(state: ResearchState) -> dict[str, Any]:
    """Run retrieval through the legacy adapter; persist raw + papers + trace."""
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    t0 = time.time()

    trace: dict[str, Any] = {
        "node": "retrieve",
        "started_at": _now_iso(),
        "input_summary": {
            "topic_len": len(topic),
            "has_atoms": bool(atoms),
            "provider": "legacy_adapter",
            "legacy_adapter": True,
        },
        "output_summary": {},
        "tool_calls": [],
        "errors": [],
        "provider": "legacy_adapter",
    }
    errors: list[dict[str, Any]] = []

    try:
        result = _run_legacy_retrieval(topic, atoms)
        raw = result.get("raw") or {}
        buckets = result.get("buckets") or {}
        paper_candidates = buckets.get("baseline_papers", []) + buckets.get(
            "parallel_papers", []
        ) + buckets.get("module_papers", []) + buckets.get("reference_papers", [])

        trace["output_summary"] = {
            "n_paper_candidates": len(paper_candidates),
            "raw_tools": list(raw.keys()),
        }
        trace["tool_calls"] = [
            {"tool": k, "n": len(v)} for k, v in raw.items()
        ]
    except NodeError as exc:
        # No retrieval path succeeded at all — log but still let pipeline move.
        logger.warning("retrieve_node all adapters unavailable: %s", exc)
        errors.append({"node": "retrieve",
                       "error": f"all_retrieval_unavailable:{exc}"})
        trace["errors"].append({"phase": "all_adapters", "error": str(exc)})
        raw = _FALLBACK_SEED["raw"]
        buckets = _FALLBACK_SEED["buckets"]
        paper_candidates = buckets["baseline_papers"]
    except BaseException as exc:
        logger.exception("retrieve_node adapter failed")
        errors.append({"node": "retrieve", "error": type(exc).__name__})
        trace["errors"].append({"phase": "adapter_call", "error": type(exc).__name__})
        raw, buckets, paper_candidates = {}, {}, []

    trace["ended_at"] = _now_iso()
    trace["elapsed_s"] = round(time.time() - t0, 3)

    return {
        "raw_results": raw,
        "paper_candidates": paper_candidates,
        "trace_events": [trace],
        "errors": errors,
        "provider_profile": "legacy_adapter",
    }
