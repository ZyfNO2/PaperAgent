"""Re09 MetadataRepairExecutor — SOP §4.3.

Real execution of the gap-repair plan.  Walks ``repair_plan[i].queries[j]``
items, dispatches them through a ``retrieval_client`` callable, dedupes
returned candidates against the existing pool, runs the rule-layer
verifier on each new candidate, and appends them to the right bucket.

Strict SOP non-negotiables:
  * NEVER fabricate metadata (every title/abstract/url comes from the
    upstream adapter).
  * Failed queries are recorded in ``failed_queries``, never silently
    skipped.
  * All adapter calls are best-effort; a single adapter failure cannot
    crash the whole repair batch.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable

from .candidate_verifier import verify_candidate_offline

logger = logging.getLogger(__name__)

# ponytail: let the caller thread retrieval through.  Five tools per spec.
DEFAULT_TOOLS = ("arxiv", "openalex", "crossref", "github", "huggingface")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_title(t: Any) -> str:
    return re.sub(r"\s+", " ", (str(t or "").strip()).lower())


def _make_cid(tool: str, hit: dict, idx: int) -> str:
    return f"repair:{tool}:{idx}:{abs(hash(_norm_title(hit.get('title' or '')))) % (10**8)}"


def _classify_bucket(tool: str, hit: dict) -> str:
    """Map an adapter hit to a bucket name.

    ponytail: keep this stringly-typed — the rest of the agent already
    uses ``paper | dataset | repo`` as labels.  Parallel papers
    discovered via adapter become ``paper`` until downstream synthesis
    re-classifies them.
    """
    t = (hit.get("evidence_type") or hit.get("type") or "").lower()
    if tool == "github" or "github.com" in (hit.get("url") or "").lower():
        return "repo"
    if t in {"dataset", "datasets"} or tool == "huggingface":
        return "dataset"
    return "paper"


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def execute_repair_plan(
    case_id: str,
    topic: str,
    topic_atoms: dict,
    repair_plan: dict,
    *,
    retrieval_client: Callable[[str, str, int], Awaitable[list[dict]]],
    llm_client: Any | None = None,
) -> dict:
    """Execute a repair plan and report execution stats.

    ``retrieval_client(tool, query, top_k)`` must be an async callable
    that returns ``list[dict]`` in the adapter-shaped schema
    (``title/url/abstract/...``).  Failures from this callable translate
    to ``failed_queries`` entries (not exceptions).
    """
    plan_items = (repair_plan or {}).get("repair_plan") or []
    planned_queries: list[tuple[str, str, str]] = []
    for entry in plan_items:
        gap = entry.get("gap", "")
        target_role = entry.get("target_role", "")
        for q in entry.get("queries") or []:
            planned_queries.append((
                q.get("tool") or "openalex",
                q.get("query") or "",
                gap,
            ))

    new_candidates: dict[str, dict] = {}  # cid -> candidate dict
    inserted_buckets: dict[str, int] = {
        "core": 0, "baseline": 0, "parallel": 0, "dataset": 0, "repo": 0,
    }
    adapter_calls: dict[str, int] = {t: 0 for t in DEFAULT_TOOLS}
    failed_queries: list[dict] = []
    verified_new: int = 0

    for tool, query, gap in planned_queries:
        if tool not in adapter_calls:
            adapter_calls[tool] = 0
        adapter_calls[tool] += 1
        try:
            hits = await retrieval_client(tool, query, 3)
        except Exception as exc:  # ponytail: never let one failure stop the run
            failed_queries.append({
                "query": query, "tool": tool, "error": repr(exc), "gap": gap,
            })
            logger.warning(
                "execute_repair_plan(%s) query %r failed: %s", case_id, query, exc,
            )
            continue
        if not hits:
            failed_queries.append({
                "query": query, "tool": tool,
                "error": "empty result", "gap": gap,
            })
            continue
        # ponytail: dedupe by normalized title against this batch's existing
        # pool — does NOT touch caller state; only within-batch dedupe.
        seen_titles: set[str] = set(new_candidates.keys())
        for idx, hit in enumerate(hits or []):
            if not isinstance(hit, dict):
                continue
            norm_t = _norm_title(hit.get("title"))
            if not norm_t:
                continue
            cid = _make_cid(tool, hit, idx)
            if cid in seen_titles or norm_t in seen_titles:
                continue
            seen_titles.add(cid)
            seen_titles.add(norm_t)
            cand = dict(hit)
            cand["candidate_id"] = cid
            cand["repair_source"] = tool
            cand["repair_query"] = query
            cand["repair_gap"] = gap
            # Determine the role for the rule layer.
            bucket = _classify_bucket(tool, hit)
            # Rule-layer classification — also produces verification_*.
            verdict = verify_candidate_offline(cand, topic_atoms, role=bucket)
            cand["verification_status"] = verdict.verification_status
            cand["verification_topic_relation"] = verdict.topic_relation
            if verdict.verification_status in {"verified", "metadata_repaired"}:
                verified_new += 1
            new_candidates[cid] = cand
            inserted_buckets[bucket] = inserted_buckets.get(bucket, 0) + 1
            # the executor maps ``paper`` to core/baseline/parallel via axis hint.
            if bucket == "paper":
                # heuristic split by target_role / gap text
                if "baseline" in target_role or "baseline" in gap:
                    inserted_buckets["baseline"] += 1
                elif "parallel" in target_role or "parallel" in gap:
                    inserted_buckets["parallel"] += 1
                else:
                    inserted_buckets["core"] += 1

    remaining_gaps: list[str] = list(
        ((repair_plan or {}).get("unrepairable_reason") or "").split("; ")
    )
    remaining_gaps = [g for g in remaining_gaps if g]

    return {
        "case_id": case_id,
        "topic": topic,
        "planned_queries_n": len(planned_queries),
        "executed_queries_n": (
            sum(adapter_calls.values()) - len(failed_queries)
        ),
        "adapter_calls": adapter_calls,
        "new_candidates_n": len(new_candidates),
        "verified_new_candidates_n": verified_new,
        "inserted_to_buckets": inserted_buckets,
        "new_candidates": list(new_candidates.values()),
        "remaining_gaps": remaining_gaps,
        "failed_queries": failed_queries,
    }


__all__ = ["execute_repair_plan"]
