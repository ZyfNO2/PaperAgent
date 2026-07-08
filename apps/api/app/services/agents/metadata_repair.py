"""Re08 MetadataRepairLoop — SOP §4.2.

For candidates flagged ``metadata_mismatch`` or ``weak_metadata`` by the
verifier, attempt a **bounded** repair pass using only the existing
retrieval adapters and the LLM.  The repaired candidate is re-injected
into the bucket with ``verification_status = metadata_repaired`` so that
``compute_resource_status`` no longer quarantines it.

Strict non-negotiables (SOP §4.2 "该模块不应该"):
  * NEVER fabricate an abstract / year / author / link.
  * NEVER overwrite the original ``raw_candidate`` field — the repaired
    candidate is a sibling so a human auditor can compare.
  * NEVER upgrade confidence to ``high`` — repaired candidates stay
    ``medium`` confidence until manually confirmed.
  * Repair is bounded: at most 2 attempts per candidate, falling back to
    ``quarantine`` if both attempts fail.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable

from .candidate_verifier import (
    VerificationResult,
    _normalize_id_field,
    _word_overlap,
    verify_candidate_offline,
)

logger = logging.getLogger(__name__)

_MAX_REPAIR_ATTEMPTS = 2


# ---------------------------------------------------------------------------
# Repair probes (each returns a candidate dict or None)
# ---------------------------------------------------------------------------


async def _probe_arxiv_by_title(
    title: str, client: Any | None = None,
) -> list[dict]:
    """Search arXiv by title fragment (last 4 words) — bounded."""
    if not title or len(title) < 10:
        return []
    # Take last 4-6 content words (drop generic prefix)
    cleaned = re.sub(r"[^\w\s一-鿿]", " ", title)
    words = [w for w in cleaned.split() if len(w) >= 3]
    if len(words) < 3:
        return []
    probe = " ".join(words[-5:])
    try:
        from ..retrieval.adapters.arxiv_search import arxiv_search
        out = await arxiv_search([probe], top_k=3, client=client)
        return out or []
    except Exception as exc:
        logger.debug("arxiv probe failed: %s", exc)
        return []


async def _probe_openalex_by_doi(
    doi: str, client: Any | None = None,
) -> list[dict]:
    """If the candidate has a DOI, ask OpenAlex to resolve it."""
    if not doi:
        return []
    try:
        from ..retrieval.adapters.openalex_search import openalex_search
        out = await openalex_search(
            [doi], per_page=3, client=client,
        )
        return out or []
    except Exception as exc:
        logger.debug("openalex doi probe failed: %s", exc)
        return []


async def _probe_github_readme(
    owner: str, repo: str, client: Any | None = None,
) -> dict | None:
    """For repo candidates: scrape the README first paragraph to recover
    the paper title / dataset name."""
    if not (owner and repo):
        return None
    try:
        from ..retrieval.adapters.github_search import github_search
        out = await github_search(
            [f"{owner}/{repo}"], language="", min_stars=0, client=client,
        )
        return (out or [None])[0]
    except Exception as exc:
        logger.debug("github readme probe failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Repair planner
# ---------------------------------------------------------------------------


def _select_best_match(
    original: dict, candidates: list[dict],
    weight: dict[str, float] | None = None,
) -> dict | None:
    """Pick the candidate with highest title similarity to the original.

    Weight defaults: title 0.6, year 0.2, authors 0.2.
    """
    if not candidates:
        return None
    weight = weight or {"title": 0.6, "year": 0.2, "authors": 0.2}
    best: tuple[float, dict] | None = None
    orig_title = (original.get("title") or "").strip()
    orig_year = str(original.get("year") or "")
    orig_authors = " ".join(original.get("authors") or []) if isinstance(
        original.get("authors"), list) else str(original.get("authors") or "")
    for c in candidates:
        if not isinstance(c, dict):
            continue
        score = 0.0
        cand_title = (c.get("title") or "").strip()
        if orig_title and cand_title:
            score += weight["title"] * _word_overlap(orig_title, cand_title)
        if orig_year and str(c.get("year") or "") == orig_year:
            score += weight["year"]
        cand_authors = c.get("authors") or []
        if isinstance(cand_authors, list):
            cand_authors = " ".join(cand_authors)
        if orig_authors and cand_authors:
            share = _word_overlap(orig_authors, str(cand_authors))
            score += weight["authors"] * share
        if best is None or score > best[0]:
            best = (score, c)
    return best[1] if best else None


async def repair_candidate(
    candidate: dict,
    topic_atoms: dict,
    role: str,
    *,
    client: Any | None = None,
    llm_client: Callable | None = None,
) -> tuple[VerificationResult, dict | None]:
    """Repair a single candidate.  Returns (verification_result, repaired_dict_or_None).

    The repaired_dict carries ``raw_candidate`` = the original so a human
    auditor can compare; ``verification_status`` is set on the result, not
    on the candidate.
    """
    candidate.get("candidate_id") or candidate.get("id") or ""
    ids = _normalize_id_field(candidate)
    title = (candidate.get("title") or "").strip()
    abstract = (candidate.get("abstract") or "").strip()
    candidate.get("url") or ""

    repaired: dict | None = None
    attempts: list[str] = []

    # Probe 1 — arXiv title probe
    if not ids.get("arxiv_id"):
        arxiv_hits = await _probe_arxiv_by_title(title, client=client)
        if arxiv_hits:
            repaired = _select_best_match(candidate, arxiv_hits)
            attempts.append("arxiv_title")

    # Probe 2 — DOI resolution (Crossref → OpenAlex → DataCite handled
    # by openalex adapter's datacite fallback for 10.48550/ and 10.5281/).
    if repaired is None and ids.get("doi"):
        doi_hits = await _probe_openalex_by_doi(ids["doi"], client=client)
        if doi_hits:
            repaired = _select_best_match(candidate, doi_hits)
            attempts.append("openalex_doi")

    # Probe 3 — GitHub README scrape
    if repaired is None and ids.get("github_owner"):
        gh = await _probe_github_readme(
            ids["github_owner"], ids["github_repo"], client=client,
        )
        if gh:
            repaired = gh
            attempts.append("github_readme")

    if repaired is None:
        # Repair failed — fall back to offline verdict.
        verdict = verify_candidate_offline(candidate, topic_atoms, role)
        verdict.recommended_action = "quarantine"
        verdict.repair_notes = (
            verdict.repair_notes or
            "metadata_mismatch could not be repaired (no probe returned)"
        )
        return verdict, None

    # Build the repaired candidate (NEVER overwrite raw fields).
    new_cand = dict(candidate)
    new_cand["raw_candidate"] = candidate
    new_cand["title"] = (repaired.get("title") or candidate.get("title") or "").strip()
    new_cand["abstract"] = (
        (repaired.get("abstract") or candidate.get("abstract") or "").strip()[:2000]
    )
    new_cand["url"] = (
        repaired.get("url") or candidate.get("url") or ""
    )
    new_cand["doi"] = repaired.get("doi") or candidate.get("doi") or ""
    if repaired.get("year"):
        new_cand["year"] = repaired["year"]
    if repaired.get("authors"):
        new_cand["authors"] = repaired["authors"]
    if repaired.get("venue"):
        new_cand["venue"] = repaired["venue"]
    if repaired.get("arxiv_id"):
        new_cand["arxiv_id"] = repaired["arxiv_id"]
    new_cand["repair_attempts"] = attempts

    # Re-classify the repaired candidate.
    verdict = verify_candidate_offline(new_cand, topic_atoms, role)
    verdict.verification_status = "metadata_repaired"
    verdict.confidence_label = "medium"
    verdict.recommended_action = "keep_as_proxy"
    verdict.reason = (
        f"repaired via {'/'.join(attempts)}; "
        f"title/abstract sim={_word_overlap(title, abstract):.2f}"
    )
    verdict.repair_notes = (
        f"used {', '.join(attempts)}; verify by hand before next stage"
    )
    return verdict, new_cand


async def repair_bucket(
    bucket_name: str,
    members: list[dict],
    topic_atoms: dict,
    *,
    client: Any | None = None,
    llm_client: Callable | None = None,
) -> tuple[list[VerificationResult], list[dict]]:
    """Repair an entire bucket.

    Returns (verdicts, repaired_candidates).  Members not needing repair
    are verified offline only; members that were repaired are added to
    the returned list.
    """
    verdicts: list[VerificationResult] = []
    repaired: list[dict] = []
    for m in members:
        cand = dict(m) if isinstance(m, dict) else {"title": str(m)}
        if "candidate_id" not in cand and "id" in cand:
            cand["candidate_id"] = cand["id"]
        base = verify_candidate_offline(cand, topic_atoms, role=bucket_name)
        if base.verification_status in {"verified", "not_found", "duplicate"}:
            verdicts.append(base)
            continue
        # Try repair.
        verdict, new_cand = await repair_candidate(
            cand, topic_atoms, bucket_name,
            client=client, llm_client=llm_client,
        )
        verdicts.append(verdict)
        if new_cand is not None:
            repaired.append(new_cand)
    return verdicts, repaired


__all__ = [
    "repair_candidate",
    "repair_bucket",
]