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
from apps.api.app.services.network_guard import NetworkPolicyGuard

logger = logging.getLogger(__name__)





from ._util import emit_trace as _emit


def _slugify(text: str) -> str:
    """Derive a kebab-case slug from a topic string."""
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def intake_node(state: ResearchState) -> dict[str, Any]:
    """Initialise intake; returns {} if trace_events already present.

    Re8.0: user-uploaded papers are NO LONGER auto-accepted into
    ``verified_papers``. Instead they are staged as ``candidate_seeds``
    and the downstream ``seed_resolver_node`` audits them (Crossref /
    arXiv authenticity check) before any promotion to evidence.
    Existing ``topic_only`` callers without ``user_papers`` see no
    behaviour change.
    """
    # Re8.0 P0-3: configure the global network guard from state so that
    # retrieval adapters enforce offline mode globally. Runs before the
    # idempotency guard so re-entry also reconfigures.
    NetworkPolicyGuard.configure(state.get("network_policy", "online"))

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
                              "errors", "candidate_seeds",
                              "entry_mode", "run_mode",
                              "network_policy", "reasoning_policy"])

    # Re8.0: default policy fields when caller did not specify
    from apps.api.app.services.agents.graph.re80_schema import default_re80_state
    re80_defaults = default_re80_state(
        entry_mode=state.get("entry_mode") or "topic_only",
        run_mode=state.get("run_mode") or "lite_chain",
        network_policy=state.get("network_policy") or "online",
        reasoning_policy=state.get("reasoning_policy") or "chain_only",
    )

    result: dict[str, Any] = {
        "case_id": case_id,
        "topic": topic,
        "provider_profile": "fast_json",
        "trace_events": [trace],
        "errors": [],
    }
    # Only set Re8.0 policy fields if caller did not specify them, so we
    # don't clobber explicit overrides passed via state.
    for k, v in re80_defaults.items():
        if k not in state or state.get(k) is None:
            result[k] = v

    # Re8.0: stage user-uploaded papers as candidate_seeds (NOT verified).
    # The seed_resolver_node is responsible for authenticity audit and
    # promotion. This closes the "fabricated DOI auto-accepts" loophole.
    user_papers = state.get("user_papers") or []
    if user_papers:
        candidate_seeds: list[dict[str, Any]] = []
        for i, p in enumerate(user_papers):
            candidate_seeds.append({
                "seed_id": p.get("seed_id") or f"user-seed-{i}",
                "title": p.get("title", ""),
                "doi": p.get("doi"),
                "arxiv_id": p.get("arxiv_id"),
                "url": p.get("url", ""),
                "authors": p.get("authors", []),
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "role": p.get("role", "unknown"),
                "raw_input": p,
            })
        result["candidate_seeds"] = candidate_seeds
        # Force entry_mode to seeded_research so seed_resolver runs
        if result.get("entry_mode", state.get("entry_mode")) == "topic_only":
            result["entry_mode"] = "seeded_research"

    return result
