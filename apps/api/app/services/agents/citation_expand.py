"""Citation expand — fetch references of strong papers, add as parallel baseline candidates.

Round 2.5 in Re02 (between multi_round_fetch and audit_candidates).

Source: each `core` / `baseline` paper with an openalex_id or DOI →
        OpenAlex `referenced_works` (free) → batch fetch titles → feed into
        CandidatePool with role_hint=parallel_baseline_candidate.

Why not arxiv API?
  arxiv has no native references endpoint (`references:` / `cited_by:` search
  returns 0 results). OpenAlex's `/works/{id}?select=referenced_works` is
  the only free way to pull structured reference lists.

What if OpenAlex fails?
  - 429 / 5xx → log to SourceLedger as `rate_limited` / `error`, skip this round
  - 404 / malformed → skip
  - empty referenced_works → skip

Ponytail: ~120 lines, no LLM, no class hierarchy, two HTTP calls per seed.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from .candidate_pool import CandidatePool

logger = logging.getLogger(__name__)


OPENALEX_WORKS_API = "https://api.openalex.org/works"
OPENALEX_HEADERS = {
    "User-Agent": "PaperAgent-Re02/1.0 (mailto:[email protected])",
    "Accept": "application/json",
}
DEFAULT_TIMEOUT = 12.0
MAX_REFS_PER_SEED = 8  # hard cap; OpenAlex can return 200+ refs on a survey

# ArXiv ID patterns (new-style 2401.01234 and legacy cs.AI/0703001)
_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE)
_ARXIV_LEGACY_RE = re.compile(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", re.IGNORECASE)


def _extract_arxiv_id_from_url(url: str | None) -> str | None:
    """Extract a raw arXiv ID (e.g. '2401.01234') from a URL or None."""
    if not url:
        return None
    m = _ARXIV_RE.search(url)
    if m:
        return m.group(1)
    m2 = _ARXIV_LEGACY_RE.search(url)
    if m2:
        return m2.group(1)
    return None


def _seed_candidates(raw: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Pick seeds: prefer arxiv papers (they have openalex_id resolved via DOI),
    then crossref DOIs. Keep top 5 to bound latency.
    """
    seeds: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for adapter in ("arxiv", "openalex", "crossref"):
        for item in raw.get(adapter) or []:
            t = (item.get("title") or "").strip()
            if not t or t.lower() in seen_titles:
                continue
            # Need at least one identifier that can resolve to OpenAlex
            if not (item.get("openalex_id") or item.get("doi") or item.get("arxiv_id")):
                continue
            seeds.append(item)
            seen_titles.add(t.lower())
            if len(seeds) >= 5:
                return seeds
    return seeds


def _to_oa_work_id(item: dict[str, Any]) -> str | None:
    """Build OpenAlex works/... path segment for the given raw item."""
    oa = item.get("openalex_id")
    if oa:
        oa = str(oa).strip().rstrip("/")
        if oa.startswith("https://openalex.org/"):
            oa = oa.rsplit("/", 1)[-1]
        if oa:
            return oa
    doi = item.get("doi")
    if doi:
        d = str(doi).strip()
        # Crossref returns "10.xxx/yyy"; OpenAlex wants "doi:10.xxx/yyy"
        if d.lower().startswith("https://doi.org/"):
            d = d[len("https://doi.org/"):]
        elif d.lower().startswith("http://dx.doi.org/"):
            d = d[len("http://dx.doi.org/"):]
        if d:
            return f"doi:{quote(d, safe='/.-_')}"
    arxiv_id = item.get("arxiv_id")
    if arxiv_id:
        return f"doi:10.48550/arXiv.{quote(arxiv_id, safe='./-_')}"
    return None


async def _fetch_work_refs(fetch, work_id: str) -> list[str]:
    """GET /works/{work_id}?select=referenced_works → list of 'W...' openalex ids."""
    url = f"{OPENALEX_WORKS_API}/{work_id}?select=referenced_works"
    try:
        data = await fetch(url, headers=OPENALEX_HEADERS, timeout=DEFAULT_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[citation_expand] referenced_works fetch failed for %s: %s", work_id, exc)
        return []
    if not isinstance(data, dict):
        return []
    refs = data.get("referenced_works") or []
    out: list[str] = []
    for r in refs:
        if not isinstance(r, str):
            continue
        # /W12345 form
        if r.startswith("https://openalex.org/"):
            r = r.rsplit("/", 1)[-1]
        if r.startswith("W") and r[1:].isdigit():
            out.append(r)
    return out[:MAX_REFS_PER_SEED]


async def _fetch_refs_metadata(fetch, ref_ids: list[str]) -> list[dict[str, Any]]:
    """GET /works/W1,W2,W3?select=id,title,publication_year,doi → list of paper dicts."""
    if not ref_ids:
        return []
    # OpenAlex accepts up to 50 ids per request via pipe
    url = f"{OPENALEX_WORKS_API}/{'|'.join(ref_ids)}?select=id,title,publication_year,doi,type"
    try:
        data = await fetch(url, headers=OPENALEX_HEADERS, timeout=DEFAULT_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[citation_expand] refs metadata fetch failed: %s", exc)
        return []
    results: list[dict[str, Any]] = []
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        if not title:
            continue
        rid = r.get("id") or ""
        if isinstance(rid, str) and rid.startswith("https://openalex.org/"):
            rid = rid.rsplit("/", 1)[-1]
        doi = r.get("doi") or ""
        if isinstance(doi, str) and doi.lower().startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        results.append({
            "title": title,
            "openalex_id": str(rid) if rid else None,
            "doi": str(doi) if doi else None,
            "year": r.get("publication_year"),
            "source": "openalex_citation",
        })
    return results


async def citation_expand(
    raw: dict[str, list[dict[str, Any]]],
    pool: CandidatePool,
    *,
    fetch,
    parsed_topic: dict | None = None,
    reviews: list[dict[str, Any]] | None = None,
    ledger=None,
    fetch_semantic_scholar=None,
) -> dict[str, int]:
    """Round 2.5: take strong seeds, pull their references, add as parallel baseline candidates.

    `fetch` is an async function (url, headers, timeout) -> dict injected by the
    orchestrator (default: use the project's `fetch_with_timeout`).

    Re03 SOP §1.3 + §1.4:
      - `_seed_candidates()` is augmented by a relevance gate (seed_relevance).
        Seeds that don't satisfy method+task/object, or ≥2 query_atoms_en
        hits, or ER-core are REJECTED (still kept in pool, just not used
        as citation seed).
      - SourceLedger NEVER pre-records "ok" before the actual fetch. Each
        seed gets its own row: `seed_selected / seed_rejected / refs_ok /
        refs_empty / refs_error`.

    Returns a stats dict: {"seeds_total", "seeds_eligible",
    "seeds_rejected", "refs_added", "round_status"} so the orchestrator
    can write the per-round delta table.
    """
    seeds = _seed_candidates(raw)
    if not seeds:
        logger.info("[citation_expand] no seed candidates with openalex_id/doi/arxiv_id — skipping")
        return {
            "seeds_total": 0,
            "seeds_eligible": 0,
            "seeds_rejected": 0,
            "refs_added": 0,
            "round_status": "no_seeds",
        }

    # Re03: apply seed_relevance gate before any network call
    from .seed_relevance import filter_seeds
    parsed_topic = parsed_topic or {}
    eligible_verdicts, rejected_verdicts = filter_seeds(seeds, parsed_topic, reviews)

    # Ledger: per-seed status (NO pre-record!)
    for v in eligible_verdicts:
        if ledger is not None:
            ledger.record(
                adapter="openalex_citation",
                query=f"seed_selected: {(v.get('_title') or '')[:60]}",
                target_role="parallel_baseline_candidate",
                round_no=2,
                round_name="reference_expansion",
                status="seed_selected",
                result_count=0,
            )
    for v in rejected_verdicts:
        if ledger is not None:
            ledger.record(
                adapter="openalex_citation",
                query=f"seed_rejected: {(v.get('_title') or '')[:60]}",
                target_role="parallel_baseline_candidate",
                round_no=2,
                round_name="reference_expansion",
                status="seed_rejected",
                result_count=0,
            )

    # Fetch references only for eligible seeds
    added = 0
    for v in eligible_verdicts:
        # find the original seed dict by candidate_id
        seed = next((s for s in seeds if s.get("candidate_id") == v.get("candidate_id")), None)
        if not seed:
            continue
        work_id = _to_oa_work_id(seed)
        if not work_id:
            if ledger is not None:
                ledger.record(
                    adapter="openalex_citation",
                    query=f"refs_error: no openalex_id for {(seed.get('title') or '')[:50]}",
                    target_role="parallel_baseline_candidate",
                    round_no=2,
                    round_name="reference_expansion",
                    status="refs_error",
                    result_count=0,
                )
            continue
        ref_ids = await _fetch_work_refs(fetch, work_id)
        meta_list: list[dict[str, Any]] = []
        if ref_ids:
            meta_list = await _fetch_refs_metadata(fetch, ref_ids)
        # Re04: Semantic Scholar fallback when openalex returned no refs.
        # S2 uses DOI / arXiv / paperId so it works even without openalex_id.
        if not meta_list and fetch_semantic_scholar is not None:
            try:
                meta_list = await fetch_semantic_scholar(
                    seed,
                    doi=seed.get("doi"),
                    arxiv_id=seed.get("arxiv_id") or _extract_arxiv_id_from_url(seed.get("url")),
                )
                if meta_list and ledger is not None:
                    ledger.record(
                        adapter="semantic_scholar_citation",
                        query=f"s2_fallback: {(seed.get('title') or '')[:50]} -> {len(meta_list)} refs",
                        target_role="parallel_baseline_candidate",
                        round_no=2,
                        round_name="reference_expansion",
                        status="refs_ok",
                        result_count=len(meta_list),
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("s2 fallback citation_expand failed: %s", exc)
                if ledger is not None:
                    ledger.record(
                        adapter="semantic_scholar_citation",
                        query=f"s2_fallback_error: {(seed.get('title') or '')[:50]}",
                        target_role="parallel_baseline_candidate",
                        round_no=2,
                        round_name="reference_expansion",
                        status="refs_error",
                        result_count=0,
                        error=str(exc)[:200],
                    )
        if not ref_ids and not meta_list:
            if ledger is not None:
                ledger.record(
                    adapter="openalex_citation",
                    query=f"refs_empty: {(seed.get('title') or '')[:50]}",
                    target_role="parallel_baseline_candidate",
                    round_no=2,
                    round_name="reference_expansion",
                    status="refs_empty",
                    result_count=0,
                )
            continue
        for m in meta_list:
            try:
                pool.add_paper(
                    title=m["title"],
                    source="openalex_citation",
                    year=m.get("year"),
                    url=None,
                    identifier=m.get("doi") or m.get("openalex_id"),
                    role_hint="parallel_baseline_candidate",
                    extra={
                        "via_seed": seed.get("title", "")[:80],
                        "via_seed_id": work_id,
                        "openalex_id": m.get("openalex_id"),
                        "matched_axis": v.get("matched_axis"),
                    },
                )
                added += 1
            except ValueError:
                # empty title already filtered
                continue
        if ledger is not None:
            ledger.record(
                adapter="openalex_citation",
                query=f"refs_ok: {(seed.get('title') or '')[:50]} -> {len(meta_list)} refs",
                target_role="parallel_baseline_candidate",
                round_no=2,
                round_name="reference_expansion",
                status="refs_ok",
                result_count=len(meta_list),
            )

    return {
        "seeds_total": len(seeds),
        "seeds_eligible": len(eligible_verdicts),
        "seeds_rejected": len(rejected_verdicts),
        "refs_added": added,
        "round_status": "ok" if (len(eligible_verdicts) > 0) else "no_eligible_seeds",
    }
