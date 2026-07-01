"""retrieval_orchestrator — Re03 SOP §3: 5-round retrieval.

Round 0: QueryMatrixBuilder (no LLM, no network)
Round 1: Broad Recall (arxiv / openalex / crossref / github)
Round 2: Dynamic Result Expansion (LLM optional, default heuristic)
Round 3: Dataset / Repo Search (github + dataset-name extraction)
Round 4: Citation Expand (openalex references, gated by seed_relevance)

Writes SourceLedger per round per call. Returns merged raw dict +
CandidatePool + per-round delta dict.

Ponytail: ~200 lines, single coroutine, no LLM by default. Caller
passes `chat_json_strict` if LLM is alive (Round 2 dynamic
expansion is optional; without LLM we use the heuristic expander
which still beats Re02's static `survey / benchmark` suffix).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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

logger = logging.getLogger(__name__)


async def run_5_round_retrieval(
    *,
    raw_topic: str,
    parsed_topic: dict,
    plan: dict,
    pool: CandidatePool,
    ledger: SourceLedger,
    fetch,
    chat_json_strict=None,
) -> dict[str, Any]:
    """Execute Re03's 5 rounds. Returns a delta dict per round for the
    per-call data delta table (Re03 SOP §1.6).
    """
    delta: dict[str, dict[str, Any]] = {}

    # Round 0: query matrix
    qm = build_query_matrix(raw_topic, parsed_topic)
    families = qm["query_families"]
    delta["R0_query_matrix"] = {
        "raw_topic": raw_topic,
        "domain_route": qm["domain_route"],
        "family_counts": {k: len(v) for k, v in families.items()},
    }

    # Round 1: Broad Recall
    # We reuse the existing `multi_round_fetch` Re02 plan structure for now.
    # Re03 will swap in a per-family dispatch in a follow-up commit.
    from .research_agent import multi_round_fetch
    raw = await multi_round_fetch(parsed_topic, plan)
    # Strip the meta keys for round-level accounting
    raw_papers = {k: v for k, v in raw.items() if k.startswith("_") is False}
    collect_papers_from_raw(raw_papers, pool)
    collect_repos_from_raw(raw_papers, pool)
    collect_mentioned_datasets(raw_papers, pool)
    delta["R1_broad_recall"] = _round_stats(raw_papers, ledger)

    # Round 2: Dynamic Result Expansion
    r2_queries = expand_from_round1(raw_papers, parsed_topic=parsed_topic)
    delta["R2_dynamic_expansion"] = {
        "n_queries": len(r2_queries),
        "queries": r2_queries[:8],
    }
    # We don't actually fire these queries at the adapter level yet
    # (Re03 SOP says LLM may refine); the expander output is recorded
    # for the synthesizer to use as Plan+R2 query suggestions.

    # Round 3: Dataset / Repo Search — reuse existing raw.github + dataset
    # extraction. Round 3 is mostly covered by collect_repos_from_raw and
    # collect_mentioned_datasets above. Here we add a github short-query
    # sweep using repos' own quoted_paper_titles.
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
        fetch=fetch,
        parsed_topic=parsed_topic,
        reviews=None,  # could pass after a Re03 ER pass; not in default flow
        ledger=ledger,
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
