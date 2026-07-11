"""LangGraph node: intake — bootstraps trace_events + provider_profile.

Pure function, no LLM, no side effects. Idempotent: if `trace_events` is already
non-empty (e.g. a prior node already initialised it) we return an empty patch so
we never clobber history on re-entry.

Output fields: case_id, provider_profile, trace_events, errors.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)





from ._util import emit_trace as _emit


def _slugify(text: str) -> str:
    """Derive a kebab-case slug from a topic string."""
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def intake_node(state: ResearchState) -> dict[str, Any]:
    """Initialise intake; returns {} if trace_events already present."""
    t0 = time.time()

    # Idempotency guard: trust existing trace.
    if state.get("trace_events"):
        return {}

    topic = state.get("topic") or ""
    case_id = state.get("case_id") or _slugify(topic)

    trace = _emit("intake", t0,
                  {"topic": topic},
                  {"ok": True},
                  [], "local", [],
                  state_keys=["case_id", "provider_profile", "trace_events",
                              "errors", "verified_papers", "seed_papers"])

    result = {
        "case_id": case_id,
        "topic": topic,
        "provider_profile": "fast_json",
        "trace_events": [trace],
        "errors": [],
    }

    # Re3.1: inject user-uploaded papers into verified_papers + seed_papers
    user_papers = state.get("user_papers") or []
    if user_papers:
        verified = []
        seeds = []
        for p in user_papers:
            entry = {
                "title": p.get("title", ""),
                "abstract": p.get("abstract", ""),
                "url": p.get("url", ""),
                "doi": p.get("doi"),
                "arxiv_id": p.get("arxiv_id"),
                "source": "user_upload",
                "verdict": "accept",
                "relation_to_topic": p.get("role", "baseline"),
                "relevance_score": 1.0,
            }
            verified.append(entry)
            seeds.append({
                "title": entry["title"],
                "url": entry["url"],
                "doi": entry.get("doi"),
                "relevance_score": 1.0,
            })
        result["verified_papers"] = verified
        result["seed_papers"] = seeds

    return result
