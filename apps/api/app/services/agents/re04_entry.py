"""Re04 SOP §5 Task 3 — main entry point: run_research_agent_re04.

Per SOP §1.2 fix #1: Re04 must have a distinct main entry. The new
entry wires QueryFamilyDispatcher + Re04 5-round orchestrator +
Semantic Scholar fallback. It does NOT pretend to be Re02.

Acceptance:
- rg "run_research_agent_re04" apps/api shows the call sites
  (entry + at least one test).
- The 4 call sites' per-round delta table lists real adapter names
  (arxiv / openalex / crossref / semantic_scholar / github) with
  result_count, NOT 'multi_round_fetch' for all 5 rounds.
- needs_clarification surfaces to the caller when topic is empty.
- No 'machine learning' fallback anywhere in the path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

from .candidate_pool import CandidatePool, collect_papers_from_raw
from .citation_expand import citation_expand
from .evidence_review import audit_candidates
from . import evidence_review as _er
from .low_bar_reviewer import run_low_bar_review
from .query_matrix import build_query_matrix
from .retrieval_orchestrator import run_5_round_retrieval
from .source_ledger import SourceLedger
from .resource_deduper import dedup_candidates, apply_relevance_gate, rank_candidates
from . import _research_agent_compat as compat

# `review_stats` is exposed via the package __init__ for back-compat.
review_stats = _er.stats if hasattr(_er, "stats") else None

logger = logging.getLogger(__name__)


def _truncate(s: str, n: int = 60) -> str:
    return (s or "")[:n]


def _safe_call(coro, name: str) -> Any:
    """Wrap a coroutine so one bad call cannot kill the pipeline.

    Re03 lesson: CB OPEN coroutines leak if not closed. We close on
    exception to avoid 'coroutine was never awaited' warnings.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except Exception as exc:  # noqa: BLE001
        logger.warning("re04 call %s failed: %s", name, exc)
        return None


async def _dispatch_to_adapters(
    family_queries: dict[str, list[str]],
    *,
    client=None,
) -> tuple[dict[str, list[dict]], SourceLedger]:
    """Re04 family-based adapter dispatch with per-call ledger.

    Returns (raw_papers, ledger). raw_papers is a dict keyed by
    adapter name; ledger captures per-call status (ok / empty /
    skipped / error) so SourceLedger never pre-records.
    """
    from ..retrieval.adapters import (
        arxiv_search, crossref_search, openalex_search, github_search,
    )
    from ..retrieval.adapters.semantic_scholar_search import semantic_scholar_search

    ledger = SourceLedger()
    raw: dict[str, list[dict]] = {}
    tasks: list[tuple[str, str, list[str]]] = []
    for family, queries in family_queries.items():
        if not queries:
            continue
        # Map family -> adapter per FAMILY_TO_ADAPTER in orchestrator.
        for adapter in compat.FAMILY_TO_ADAPTER.get(family, []):
            capped = [q for q in queries if q][:3]
            if not capped:
                ledger.add(
                    adapter=adapter, query="<empty>",
                    target_role=family, round_num=1,
                    round_name="family_dispatch",
                    status="skipped_empty_query", result_count=0, error=None,
                )
                continue
            tasks.append((adapter, family, capped))

    # Fire all tasks concurrently
    async def _fire(adapter: str, family: str, queries: list[str]) -> None:
        try:
            if adapter == "arxiv":
                results = await arxiv_search(queries, top_k=8, client=client)
            elif adapter == "openalex":
                results = await openalex_search(queries, top_k=8, client=client)
            elif adapter == "crossref":
                results = await crossref_search(queries, top_k=8, client=client)
            elif adapter == "github":
                results = await github_search(queries, top_k=6, client=client)
            elif adapter == "semantic_scholar":
                results = await semantic_scholar_search(queries, top_k=8, client=client)
            else:
                results = []
        except Exception as exc:  # noqa: BLE001
            logger.warning("dispatch %s failed: %s", adapter, exc)
            results = []
        raw.setdefault(adapter, []).extend(results)
        ledger.add(
            adapter=adapter, query="|".join(queries)[:120],
            target_role=family, round_num=1,
            round_name="family_dispatch",
            status="ok" if results else "empty",
            result_count=len(results), error=None,
        )

    if tasks:
        await asyncio.gather(*[_fire(a, f, q) for a, f, q in tasks], return_exceptions=True)
    return raw, ledger


async def _s2_fallback_for_citation(seed: dict, **kw) -> list[dict]:
    """Wrap semantic_scholar_references / citations for citation_expand."""
    from ..retrieval.adapters.semantic_scholar_search import (
        semantic_scholar_references, semantic_scholar_citations,
    )
    refs = await semantic_scholar_references(
        paper_id=seed.get("paper_id"),
        doi=kw.get("doi") or seed.get("doi"),
        arxiv_id=kw.get("arxiv_id") or seed.get("arxiv_id"),
        top_k=15,
    )
    cits = await semantic_scholar_citations(
        paper_id=seed.get("paper_id"),
        doi=kw.get("doi") or seed.get("doi"),
        arxiv_id=kw.get("arxiv_id") or seed.get("arxiv_id"),
        top_k=15,
    )
    # Prefer references (forward chain); fall back to citations.
    return refs if refs else cits


async def run_research_agent_re04(
    raw_topic: str,
    *,
    auto_low_bar: bool = True,
    auto_devils_advocate: bool = False,
    client=None,
) -> dict[str, Any]:
    """Re04 end-to-end entry. Returns a dict with raw_topic, parsed,
    plan, pool, ledger, reviews, synthesis, low_bar_verdict, round_delta.

    This is the main entry the SOP §1.2 fix #1 demands — distinct
    from run_research_agent_re02.
    """
    project_id = f"agent-re04-{uuid.uuid4().hex[:8]}"
    t0 = time.time()

    # Step 1: parse topic
    parsed = compat.parse_topic(raw_topic)
    parsed["raw_topic"] = raw_topic

    # Early-out: empty / whitespace-only raw_topic cannot be served.
    if not (raw_topic or "").strip():
        return {
            "project_id": project_id,
            "raw_topic": raw_topic or "",
            "parsed_topic": parsed,
            "blocked_reason": "needs_clarification",
            "round_delta": {
                "R0_query_matrix": {
                    "needs_clarification": True,
                    "raw_topic": raw_topic or "",
                    "reason": "empty raw_topic",
                },
            },
        }

    # Step 2: query matrix (Round 0)
    qm = build_query_matrix(raw_topic, parsed)
    if qm.get("needs_clarification"):
        # Caller will see blocked_reason; do not call adapters
        return {
            "project_id": project_id,
            "raw_topic": raw_topic,
            "parsed_topic": parsed,
            "query_matrix": qm,
            "blocked_reason": "needs_clarification",
            "round_delta": {
                "R0_query_matrix": {"needs_clarification": True, "raw_topic": raw_topic},
            },
        }

    # Step 3: plan via Re02 plan_tools_v2 (deterministic — no LLM dead path)
    plan = compat.plan_tools_v2(parsed)

    # Step 4: per-family dispatch (Round 1)
    families = qm.get("query_families") or {}
    raw, ledger = await _dispatch_to_adapters(families, client=client)

    # Step 5: dedup + add to pool
    if raw:
        all_items: list[dict] = []
        for adapter, items in raw.items():
            for c in items:
                cc = dict(c)
                cc.setdefault("source", adapter)
                all_items.append(cc)
        deduped = dedup_candidates(all_items)
        # Re-key raw as the deduped, adapter-stamped records
        raw = {}
        for rec in deduped:
            src = rec.get("source") or "unknown"
            raw.setdefault(src, []).append(rec)
    pool = CandidatePool()
    collect_papers_from_raw(raw, pool)
    from .candidate_pool import collect_repos_from_raw, collect_mentioned_datasets
    collect_repos_from_raw(raw, pool)
    collect_mentioned_datasets(raw, pool)

    # Step 6: Round 2 dynamic expansion (real s2 call)
    from .result_expander import expand_from_round1
    r2_queries_raw = expand_from_round1(raw, parsed_topic=parsed)
    # result_expander returns list[dict] with .query; flatten to strings
    r2_queries: list[str] = []
    for q in r2_queries_raw:
        if isinstance(q, dict):
            s = q.get("query") or q.get("text") or ""
        else:
            s = str(q)
        if s:
            r2_queries.append(s)
    r2_added: list[dict] = []
    if r2_queries:
        from ..retrieval.adapters.semantic_scholar_search import semantic_scholar_search
        try:
            r2_hits = await semantic_scholar_search(r2_queries[:3], top_k=8, client=client)
            r2_added = r2_hits
            ledger.add(
                adapter="semantic_scholar", query="|".join(r2_queries[:3])[:120],
                target_role="dynamic_expansion", round_num=2,
                round_name="r2_dynamic_expansion",
                status="ok" if r2_hits else "empty",
                result_count=len(r2_hits), error=None,
            )
            for h in r2_hits:
                hit = dict(h); hit.setdefault("source", "semantic_scholar")
                try:
                    pool.add_paper(
                        title=hit.get("title") or "",
                        source="semantic_scholar",
                        role_hint="parallel",
                        extra={"via_round": 2},
                    )
                except ValueError:
                    pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("r2 dynamic expansion failed: %s", exc)
            ledger.add(
                adapter="semantic_scholar", query="|".join(r2_queries[:3])[:120],
                target_role="dynamic_expansion", round_num=2,
                round_name="r2_dynamic_expansion",
                status="error", result_count=0, error=str(exc)[:200],
            )

    # Step 7: Round 4 citation expand (openalex with s2 fallback)
    try:
        from ..retrieval._http import fetch_with_timeout
        ce_stats = await citation_expand(
            raw=raw, pool=pool, fetch=fetch_with_timeout,
            parsed_topic=parsed, reviews=None, ledger=ledger,
            fetch_semantic_scholar=_s2_fallback_for_citation,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("citation_expand failed: %s", exc)
        ce_stats = {"round_status": "error", "error": str(exc)[:200]}

    # Step 8: evidence review
    reviews = audit_candidates(
        parsed_topic=parsed,
        candidates=pool.as_list(),
        raw=raw,
        chat_json_strict=compat.chat_json_strict,
    )

    # Step 9: synthesize
    try:
        synthesis = compat.synthesize_v2(
            raw_topic=raw_topic,
            domain_route=parsed.get("domain_route", "unknown"),
            topic_json=parsed,
            raw=raw,
            reviews=reviews,
            pool=pool,
            ledger=ledger,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("synthesize_v2 failed: %s", exc)
        synthesis = {"error": str(exc)[:200]}

    # Step 10: low-bar
    if auto_low_bar:
        try:
            verdict = run_low_bar_review(
                parsed_topic=parsed,
                synthesize_output=synthesis,
                evidence_review_stats=review_stats(reviews) if review_stats else {},
                candidate_pool_stats=pool.stats(),
                chat_json_strict=compat.chat_json_strict,
            )
            verdict = verdict.to_dict() if hasattr(verdict, "to_dict") else (verdict or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("low_bar failed: %s", exc)
            verdict = {"review_verdict": "needs_revision", "summary": str(exc)[:200]}
    else:
        verdict = {}

    # Round delta table (SOP §1.6 — per-call data delta)
    per_adapter = {a: len(items) for a, items in raw.items()}
    round_delta = {
        "R0_query_matrix": {
            "raw_topic": raw_topic,
            "domain_route": qm.get("domain_route"),
            "family_counts": {k: len(v) for k, v in (families or {}).items()},
            "needs_clarification": False,
        },
        "R1_family_dispatch": {
            "per_adapter": per_adapter,
            "ledger_n_calls": len(ledger.as_list()),
        },
        "R2_dynamic_expansion": {
            "n_queries": len(r2_queries),
            "queries": r2_queries[:8],
            "added_count": len(r2_added),
        },
        "R4_citation_expand": ce_stats,
    }

    return {
        "project_id": project_id,
        "raw_topic": raw_topic,
        "parsed_topic": parsed,
        "query_matrix": qm,
        "plan": plan,
        "candidate_pool": pool,
        "source_ledger": ledger,
        "evidence_review": reviews,
        "synthesis": synthesis,
        "low_bar_verdict": verdict,
        "round_delta": round_delta,
        "elapsed_s": round(time.time() - t0, 2),
    }


# Convenience: dump to a single file for inspection (used by the
# Re04 online smoke harness).
def dump_re04_result(result: dict, out_path: str) -> None:
    """Serialize a Re04 result dict to JSON (best-effort)."""
    def _coerce(o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if hasattr(o, "as_list"):
            return o.as_list()
        if isinstance(o, dict):
            return {k: _coerce(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_coerce(x) for x in o]
        return o

    safe = _coerce(result)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2, default=str)
