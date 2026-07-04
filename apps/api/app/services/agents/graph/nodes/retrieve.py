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


def _run_legacy_retrieval(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Run the existing search_reflection_loop synchronously, return payload.

    When the legacy module fails to import (upstream churn), fall back to a
    deterministic lightweight seed so the pipeline keeps moving. All paths are
    wrapped with legacy_adapter=true in the trace.
    """
    try:
        from apps.api.app.services.agents import search_reflection_loop as srl
    except ImportError as exc:
        raise NodeError(f"legacy adapter not importable: {exc.__class__.__name__}: {exc}") from exc

    # Adapter bridge: loop expects topic string; parsed_atoms may not be
    # supported in this revision.
    try:
        coro = srl.run_search_reflection_loop(raw_topic=topic, parsed_atoms=atoms)
    except TypeError:
        coro = srl.run_search_reflection_loop(raw_topic=topic)
    return asyncio.run(coro)


_FALLBACK_SEED = {
    "buckets": {
        "baseline_papers": [
            {
                "title": "A lightweight baseline (placeholder — legacy adapter was not importable)",
                "abstract": "Synthesised placeholder because the legacy search_reflection_loop "
                            "could not be imported. Real retrieval will be re-attempted in Loop 3+.",
                "source": "placeholder-adapter",
                "note": "fallback_seed",
            },
        ],
        "parallel_papers": [],
        "module_papers": [],
        "reference_papers": [],
    },
    "raw": {"placeholder": []},
}


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
        # Legacy adapter import failed (upstream churn) — fallback seed so the
        # pipeline can still complete and we can keep Loops going.
        logger.warning("retrieve_node legacy adapter unavailable: %s", exc)
        errors.append({"node": "retrieve",
                       "error": f"legacy_adapter_import_error:{exc}"})
        trace["errors"].append({"phase": "adapter_import", "error": str(exc)})
        raw = _FALLBACK_SEED["raw"]
        buckets = _FALLBACK_SEED["buckets"]
        paper_candidates = buckets["baseline_papers"]
        trace["legacy_adapter_fallback"] = True
        trace["errors"][0]["fallback_used"] = "placeholder_seed"
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
        "trace_events": list(state.get("trace_events") or []) + [trace],
        "errors": list(state.get("errors") or []) + errors,
        "provider_profile": "legacy_adapter",
    }
