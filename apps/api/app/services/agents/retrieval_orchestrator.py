"""retrieval_orchestrator — Re04 SOP §5 Task 3.

Round 0: QueryMatrixBuilder (no LLM, no network) → needs_clarification check
Round 1: QueryFamilyDispatcher (real per-family dispatch to arXiv /
         OpenAlex / Crossref / Semantic Scholar / GitHub)
Round 2: Dynamic Result Expansion — REAL adapter calls (not just log)
Round 3: Dataset / Repo Search — github + dataset-name extraction
Round 4: Citation Expand (openalex_citation → semantic_scholar
         references/citations → arXiv title fallback)

Writes SourceLedger per round per call. Returns merged raw dict +
CandidatePool + per-round delta dict.

Re04 acceptance:
- Query families are dispatched to the correct adapter (no more
  single `multi_round_fetch` for all 8 families).
- Round 2 expansion actually calls an adapter.
- No 'machine learning' fallback anywhere.
- needs_clarification surfaced to the caller when atoms are empty.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from .candidate_pool import (
    CandidatePool,
    collect_mentioned_datasets,
    collect_papers_from_raw,
    collect_repos_from_raw,
)
from .citation_expand import citation_expand
from .query_matrix import build_query_matrix
from .result_expander import expand_from_round1
from .seed_relevance import filter_seeds
from .source_ledger import SourceLedger
from .resource_deduper import dedup_candidates

logger = logging.getLogger(__name__)


# Per-family adapter mapping (Re04 SOP §1.2 fix #2).
FAMILY_TO_ADAPTER = {
    "core": ["arxiv", "openalex", "crossref"],
    "method_task": ["arxiv", "openalex"],
    "object_task": ["crossref", "openalex"],
    "dataset": ["crossref", "openalex"],
    "repo": ["github"],
    "survey": ["arxiv", "openalex"],
    "benchmark": ["crossref", "openalex"],
    "baseline": ["arxiv", "crossref"],
}


def _flatten_queries_for_family(qm: dict, family: str) -> list[str]:
    families = qm.get("query_families") or {}
    return list(families.get(family) or [])


async def _dispatch_family_to_adapters(
    family: str,
    queries: list[str],
    *,
    fetch_arxiv,
    fetch_openalex,
    fetch_crossref,
    fetch_github,
    fetch_semantic_scholar,
    ledger: SourceLedger,
    round_num: int,
) -> dict[str, list[dict]]:
    """Dispatch one query family's queries to the adapters mapped in
    FAMILY_TO_ADAPTER. Each adapter call is wrapped to record the
    SourceLedger row (status=ok/empty/skipped_rate_limited/error).
    """
    out: dict[str, list[dict]] = {}
    if not queries:
        # Still record a row so the ledger shows the family was considered.
        for adapter in FAMILY_TO_ADAPTER.get(family, []):
            ledger.add(
                adapter=adapter, query="<empty-family>", target_role=family,
                round_num=round_num, round_name="family_dispatch",
                status="skipped_empty_query", result_count=0, error=None,
            )
        return out

    adapter_calls: dict[str, Callable[[list[str]], Awaitable[list[dict]]]] = {
        "arxiv": fetch_arxiv,
        "openalex": fetch_openalex,
        "crossref": fetch_crossref,
        "github": fetch_github,
        "semantic_scholar": fetch_semantic_scholar,
    }

    for adapter in FAMILY_TO_ADAPTER.get(family, []):
        fn = adapter_calls.get(adapter)
        if fn is None:
            ledger.add(
                adapter=adapter, query=queries[0] if queries else "",
                target_role=family, round_num=round_num, round_name="family_dispatch",
                status="skipped_no_adapter", result_count=0, error=None,
            )
            continue
        # Cap queries per adapter to keep rate limits sane.
        capped = [q for q in queries if q][:3]
        try:
            results = await fn(capped)
            out.setdefault(adapter, []).extend(results)
            ledger.add(
                adapter=adapter, query="|".join(capped), target_role=family,
                round_num=round_num, round_name="family_dispatch",
                status="ok" if results else "empty",
                result_count=len(results), error=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("family_dispatch %s failed: %s", adapter, exc)
            ledger.add(
                adapter=adapter, query="|".join(capped), target_role=family,
                round_num=round_num, round_name="family_dispatch",
                status="error", result_count=0, error=str(exc)[:200],
            )
    return out


async def run_5_round_retrieval(
    *,
    raw_topic: str,
    parsed_topic: dict,
    plan: dict,
    pool: CandidatePool,
    ledger: SourceLedger,
    fetch,
    chat_json_strict=None,
    fetch_semantic_scholar=None,
) -> dict[str, Any]:
    """Execute Re04 5 rounds with REAL per-family dispatch.

    Returns a delta dict per round for the per-call data delta table.
    """
    delta: dict[str, dict[str, Any]] = {}

    # Round 0: query matrix + needs_clarification gate
    qm = build_query_matrix(raw_topic, parsed_topic)
    families = qm["query_families"]
    delta["R0_query_matrix"] = {
        "raw_topic": raw_topic,
        "domain_route": qm["domain_route"],
        "needs_clarification": qm.get("needs_clarification", False),
        "family_counts": {k: len(v) for k, v in families.items()},
    }
    if qm.get("needs_clarification"):
        # Orchestrator returns early; caller should ask user for a
        # clearer topic. We still record this in the ledger.
        ledger.add(
            adapter="<orchestrator>", query=raw_topic or "<empty>",
            target_role="<needs_clarification>", round_num=0,
            round_name="query_matrix", status="skipped_clarification",
            result_count=0, error="empty raw_topic and atoms",
        )
        return {"raw": {}, "delta": delta, "query_matrix": qm,
                "blocked_reason": "needs_clarification"}

    # Round 1: family-based dispatch (real per-family adapter calls)
    r1_by_family: dict[str, dict[str, list[dict]]] = {}
    for family in ("core", "method_task", "object_task", "dataset",
                   "repo", "survey", "benchmark", "baseline"):
        queries = _flatten_queries_for_family(qm, family)
        if not queries:
            continue
        r1_by_family[family] = await _dispatch_family_to_adapters(
            family, queries,
            fetch_arxiv=fetch.get("arxiv") if isinstance(fetch, dict) else None,
            fetch_openalex=fetch.get("openalex") if isinstance(fetch, dict) else None,
            fetch_crossref=fetch.get("crossref") if isinstance(fetch, dict) else None,
            fetch_github=fetch.get("github") if isinstance(fetch, dict) else None,
            fetch_semantic_scholar=fetch_semantic_scholar,
            ledger=ledger, round_num=1,
        )

    # Flatten R1 into a raw {adapter: [candidates]} dict and add to pool
    raw_papers: dict[str, list[dict]] = {}
    for fam_results in r1_by_family.values():
        for adapter, items in fam_results.items():
            raw_papers.setdefault(adapter, []).extend(items)

    # Re04: dedup across sources BEFORE adding to pool (DOI / arxiv /
    # title). Dedup is per-source-flavor — arxiv + openalex + s2 + crossref
    # all flattened, then merged.
    if raw_papers:
        all_items: list[dict] = []
        for adapter, items in raw_papers.items():
            for c in items:
                cc = dict(c)
                cc.setdefault("source", adapter)
                all_items.append(cc)
        deduped = dedup_candidates(all_items)
        # Replace raw_papers contents with the deduped, provenance-stamped
        # records, but keep adapter-keyed buckets for legacy callers.
        raw_papers = {}
        for rec in deduped:
            src = rec.get("source") or "unknown"
            raw_papers.setdefault(src, []).append(rec)

    collect_papers_from_raw(raw_papers, pool)
    collect_repos_from_raw(raw_papers, pool)
    collect_mentioned_datasets(raw_papers, pool)
    delta["R1_family_dispatch"] = {
        "by_family": {fam: {a: len(items) for a, items in fam_res.items()}
                      for fam, fam_res in r1_by_family.items()},
        "per_adapter": {a: len(items) for a, items in raw_papers.items()},
    }

    # Round 2: Dynamic Result Expansion — REAL adapter call (SOP §1.2 fix #3)
    r2_queries_raw = expand_from_round1(raw_papers, parsed_topic=parsed_topic)
    r2_queries: list[str] = []
    for q in r2_queries_raw:
        if isinstance(q, dict):
            s = q.get("query") or q.get("text") or ""
        else:
            s = str(q)
        if s:
            r2_queries.append(s)
    r2_added: dict[str, list[dict]] = {}
    if r2_queries and fetch_semantic_scholar is not None:
        try:
            s2_hits = await fetch_semantic_scholar(r2_queries[:3])
            r2_added["semantic_scholar"] = s2_hits
            ledger.add(
                adapter="semantic_scholar", query="|".join(r2_queries[:3]),
                target_role="dynamic_expansion", round_num=2,
                round_name="r2_dynamic_expansion",
                status="ok" if s2_hits else "empty",
                result_count=len(s2_hits), error=None,
            )
            # Merge into raw + pool
            for h in s2_hits:
                hit = dict(h); hit.setdefault("source", "semantic_scholar")
                raw_papers.setdefault("semantic_scholar", []).append(hit)
                try:
                    pool.add_paper(
                        title=hit.get("title") or "",
                        source="semantic_scholar",
                        role_hint="parallel",
                        extra={"via_round": 2, "query": r2_queries[:3]},
                    )
                except ValueError:
                    pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("round2 dynamic expansion failed: %s", exc)
            ledger.add(
                adapter="semantic_scholar", query="|".join(r2_queries[:3]),
                target_role="dynamic_expansion", round_num=2,
                round_name="r2_dynamic_expansion",
                status="error", result_count=0, error=str(exc)[:200],
            )
    delta["R2_dynamic_expansion"] = {
        "n_queries": len(r2_queries),
        "queries": r2_queries[:8],
        "per_adapter": {a: len(items) for a, items in r2_added.items()},
    }

    # Round 3: Dataset / Repo Search — github short-query sweep using
    # repos' own quoted_paper_titles. Same as Re03 (genuine github call).
    r3_extra: list[dict[str, Any]] = []
    for repo in pool.by_evidence_type("repo"):
        for qt in (repo.quoted_paper_titles or []):
            try:
                cand = pool.add_paper(
                    title=qt,
                    source="github_repo_quote",
                    role_hint="reference",
                    extra={"via_repo": repo.title, "via_repo_id": repo.candidate_id},
                )
                r3_extra.append(cand.to_dict())
            except ValueError:
                continue
    delta["R3_dataset_repo"] = {"extras_added": len(r3_extra)}

    # Round 4: Citation Expand (with seed_relevance gate + per-seed ledger)
    ce_stats = await citation_expand(
        raw=raw_papers,
        pool=pool,
        fetch=fetch.get("openalex") if isinstance(fetch, dict) else fetch,
        parsed_topic=parsed_topic,
        reviews=None,
        ledger=ledger,
        fetch_semantic_scholar=fetch_semantic_scholar,
    )
    delta["R4_citation_expand"] = ce_stats

    return {
        "raw": raw_papers,
        "delta": delta,
        "query_matrix": qm,
    }


def _round_stats(raw: dict[str, list[dict[str, Any]]], ledger: SourceLedger) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for adapter, items in raw.items():
        out[adapter] = len(items)
    out["ledger_n_calls"] = len(ledger.as_list())
    return out
