"""Re8.0 Seed Resolver — audited entry point for user-supplied papers.

Replaces the legacy ``intake_node`` behaviour where ``user_papers`` were
directly injected into ``verified_papers`` with ``verdict="accept"``. That
path bypassed all authenticity checks and let fabricated DOIs / model-
hallucinated titles enter the evidence pool unchallenged (Re8.0 §3, §6.2).

This node is the deterministic Spine part of the Seed Resolver sub-graph
described in §6.1. Concurrency (parallel PDF / metadata fetches) is handled
inline with ``asyncio.gather``; the final authenticity verdict is always
issued here, never delegated to a sub-agent.

Decision rules (§6.2):
  - DOI resolves + title/authors roughly match  → verified
  - arXiv / publisher page exists + metadata matches → verified
  - Only a search snippet, no authoritative landing page → ambiguous
  - DOI points to a different paper → not_found + identifier_mismatch
  - Title close but author/year conflict → ambiguous + repair_hint
  - Local PDF parseable, no DOI → verified (local) with source=local_pdf
  - Model-generated title not findable → not_found

Only ``verified`` cards with at least one stable identifier are promoted
to ``verified_papers``. ``ambiguous`` / ``not_found`` cards stay in
``seed_cards`` for downstream reasoning but never become evidence.

The node is a no-op when ``entry_mode == "topic_only"`` or when there are
no ``candidate_seeds`` to resolve, so existing topic-only callers see no
behaviour change.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.re80_schema import (
    SEED_INPUT_FORMS,
    is_seed_evidence_eligible,
    make_ledger_entry,
    make_seed_card,
    validate_seed_card,
)
from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


# ── Identifier normalisation ────────────────────────────────────────────────

import re as _re

_DOI_RE = _re.compile(r"10\.\d{4,9}/\S+$")
# Anchored pattern for validating a standalone arXiv ID
_ARXIV_RE = _re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$|^[a-z\-]+(?:\.[a-z\-]+)?/\d{7}$",
                         _re.IGNORECASE)
# Unanchored pattern for extracting an arXiv ID from a URL (Re8.0 P1-1 fix:
# ^...$ anchoring + .search() never matched URLs like https://arxiv.org/abs/2401.00001).
# P1-1b: also match old-style subject-class IDs like cs.LG/0703001, math.AT/0701001
# (subject class may contain dots, hyphens, and mixed case).
_ARXIV_URL_RE = _re.compile(
    r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-.]+/\d{7})", _re.IGNORECASE,
)


# Fields that may live either at the top-level of a candidate seed payload
# or nested inside its ``raw_input`` dict. Used by ``_normalize_seed_payload``
# to flatten the nested form onto the top-level so downstream classification
# + metadata fetch always see a canonical flat payload.
_SEED_NORMALIZE_FIELDS = (
    "doi", "arxiv_id", "url", "title",
    "pdf_path", "pdf_bytes",
    "authors", "year", "abstract",
)


def _normalize_seed_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten ``raw_input`` fields onto the top-level of a seed payload.

    Re8.0 accepts candidate seeds in two equivalent forms:

    1. Flat top-level fields (``doi``, ``arxiv_id``, ``url``, ``title``,
       ``pdf_path``) — the canonical Resolver contract.
    2. Nested ``raw_input`` dict carrying the same fields — the form
       emitted by ``re80_seeded_demo.py`` and several API callers.

    This helper returns a new dict where any identifier / metadata field
    that is missing (or empty) at the top-level is filled in from the
    matching ``raw_input`` entry. Top-level fields always win: an explicit
    top-level value is never overwritten by ``raw_input``. The original
    ``raw_input`` dict itself is preserved verbatim so that audit trails
    and ``pdf_bytes`` consumers keep working.

    The input dict is not mutated.
    """
    if not isinstance(payload, dict):
        return {}
    normalized = dict(payload)
    raw = normalized.get("raw_input")
    if not isinstance(raw, dict):
        return normalized
    for field in _SEED_NORMALIZE_FIELDS:
        top_val = normalized.get(field)
        if top_val in (None, "", [], {}):
            raw_val = raw.get(field)
            if raw_val not in (None, "", [], {}):
                normalized[field] = raw_val
    return normalized


def _classify_input(payload: dict[str, Any]) -> tuple[str, str | None]:
    """Return (input_form, identifier) for a candidate seed payload.

    input_form is one of SEED_INPUT_FORMS. identifier is the canonical
    DOI / arXiv id when available, else None.

    The payload is normalized first via ``_normalize_seed_payload`` so
    that identifier fields nested inside ``raw_input`` are visible to
    the classifier. This makes the Resolver tolerant of both the flat
    top-level contract and the nested ``raw_input`` form (Re8.0 P0-1).
    """
    payload = _normalize_seed_payload(payload)
    doi = (payload.get("doi") or "").strip()
    if doi:
        return "doi", doi
    arxiv = (payload.get("arxiv_id") or "").strip()
    if arxiv:
        return "arxiv", arxiv
    url = (payload.get("url") or "").strip()
    if url:
        # Try to extract arxiv id from URL (P1-1: use unanchored pattern)
        if "arxiv.org" in url.lower():
            m = _ARXIV_URL_RE.search(url)
            if m:
                return "arxiv", m.group(1)
        return "url", url
    # PDF is a stronger signal than title — check before title so a
    # candidate carrying both pdf_path and title is treated as a PDF.
    if payload.get("pdf_path") or payload.get("pdf_bytes"):
        return "pdf", None
    title = (payload.get("title") or "").strip()
    if title:
        return "title", None
    return "citation", None


# ── Async metadata fetchers (Crossref / arXiv) ──────────────────────────────

async def _fetch_crossref(doi: str) -> dict[str, Any] | None:
    """Fetch metadata from Crossref by DOI. Returns None on any failure."""
    import httpx
    try:
        async with httpx.AsyncClient(
            timeout=10.0, proxy=None, verify=False, follow_redirects=True
        ) as client:
            resp = await client.get(
                f"https://api.crossref.org/works/{doi}",
                headers={"User-Agent": "PaperAgent/1.0 (mailto:[email protected])"},
            )
            if resp.status_code != 200:
                return None
            item = resp.json().get("message", {}) or {}
            raw_titles = item.get("title") or []
            title = str(raw_titles[0]) if raw_titles else ""
            authors = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in (item.get("author") or [])
                if isinstance(a, dict)
            ]
            issued = item.get("issued") or {}
            parts = issued.get("date-parts") if isinstance(issued, dict) else None
            year = None
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                y = parts[0][0]
                if isinstance(y, int):
                    year = y
            res = item.get("resource") or {}
            primary = res.get("primary") if isinstance(res, dict) else None
            url = primary.get("URL", "") if isinstance(primary, dict) else ""
            abstract = item.get("abstract") or ""
            return {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "canonical_url": url,
                "abstract": abstract[:800] if abstract else "",
            }
    except Exception as exc:
        logger.debug("crossref fetch failed for %s: %s", doi, exc)
        return None


async def _fetch_arxiv(arxiv_id: str) -> dict[str, Any] | None:
    """Fetch metadata from arXiv API. Returns None on any failure."""
    import httpx
    try:
        async with httpx.AsyncClient(
            timeout=10.0, proxy=None, verify=False, follow_redirects=True
        ) as client:
            resp = await client.get(
                f"https://export.arxiv.org/api/query?id_list={arxiv_id}",
            )
            if resp.status_code != 200:
                return None
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = "{http://www.w3.org/2005/Atom}"
            entry = root.find(f"{ns}entry")
            if entry is None:
                return None
            t_elem = entry.find(f"{ns}title")
            title = "".join(t_elem.itertext()).strip() if t_elem is not None else ""
            s_elem = entry.find(f"{ns}summary")
            abstract = "".join(s_elem.itertext()).strip() if s_elem is not None else ""
            id_elem = entry.find(f"{ns}id")
            url = "".join(id_elem.itertext()).strip() if id_elem is not None else ""
            authors: list[str] = []
            for a_elem in entry.findall(f"{ns}author"):
                n_elem = a_elem.find(f"{ns}name")
                if n_elem is not None:
                    authors.append("".join(n_elem.itertext()).strip())
            year = None
            published = entry.find(f"{ns}published")
            if published is not None:
                ptext = "".join(published.itertext()).strip()
                if len(ptext) >= 4 and ptext[:4].isdigit():
                    year = int(ptext[:4])
            return {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": None,
                "arxiv_id": arxiv_id,
                "canonical_url": url,
                "abstract": abstract[:800] if abstract else "",
            }
    except Exception as exc:
        logger.debug("arxiv fetch failed for %s: %s", arxiv_id, exc)
        return None


# ── Authenticity decision ───────────────────────────────────────────────────

def _titles_agree(a: str, b: str) -> bool:
    """Loose title agreement check (case-insensitive, punctuation-tolerant)."""
    import re as _re
    norm = lambda s: _re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    # Allow either to be a substring of the other (covers truncated titles)
    return na == nb or na in nb or nb in na


def _author_lastname(author: str) -> str:
    """Extract a normalised surname from an author string.

    Handles both ``"Devlin, J."`` (surname first) and ``"Jacob Devlin"``
    (given first) forms. Crossref returns ``"given family"`` while user
    seeds often carry ``"Family, G."`` — without this normalisation the
    existence check rejects papers whose authors are actually identical
    (Re8.0 P0-B fix).
    """
    a = (author or "").strip().lower()
    if not a:
        return ""
    if "," in a:
        return a.split(",", 1)[0].strip()
    parts = a.split()
    return parts[-1] if parts else ""


def _decide_existence(
    candidate: dict[str, Any],
    fetched: dict[str, Any] | None,
) -> tuple[str, str | None]:
    """Return (existence_status, repair_hint).

    repair_hint is None when status == verified; otherwise it carries a
    short reason that downstream Repair Resolve or the user can act on.
    """
    if fetched is None:
        # Could not confirm via authoritative source
        title = (candidate.get("title") or "").strip()
        if title:
            return "ambiguous", "no authoritative landing page; consider Repair via author/year"
        return "not_found", "no identifier and no title; cannot verify"

    # Fetched metadata exists — check consistency
    user_title = (candidate.get("title") or "").strip()
    fetched_title = fetched.get("title") or ""
    if user_title and not _titles_agree(user_title, fetched_title):
        # Title mismatch: could be DOI pointing to a different paper, or
        # a close-but-not-identical match. Distinguish by checking if the
        # user-supplied DOI's fetched title shares any token with user title.
        return "ambiguous", f"title mismatch: user='{user_title[:60]}' vs fetched='{fetched_title[:60]}'"

    # Re8.0 P0-B: compare authors by normalised LAST NAME only.
    # User seeds typically carry ``"Devlin, J."`` (surname first) while
    # Crossref returns ``"Jacob Devlin"`` (given first). A strict full-
    # string set intersection rejects these identical authors, leaving
    # every DOI-verified seed stuck at existence_status=ambiguous.
    user_lastnames = {
        _author_lastname(a) for a in (candidate.get("authors") or []) if a
    }
    fetched_lastnames = {
        _author_lastname(a) for a in (fetched.get("authors") or []) if a
    }
    if (
        user_lastnames
        and fetched_lastnames
        and not (user_lastnames & fetched_lastnames)
    ):
        return "ambiguous", "author set does not intersect; possible identifier_mismatch"

    return "verified", None


# ── Title-based search (Seed Repair) ─────────────────────────────────────────

def _normalize_title_hit(hit: dict[str, Any], source: str) -> dict[str, Any]:
    """Map a crossref_search / semantic_scholar_search hit to the schema
    expected by ``_decide_existence``: ``{title, authors, year, doi,
    canonical_url, abstract}``.

    Both adapters already return unified-schema dicts, but field names
    differ slightly (crossref uses ``doi`` / ``url``; semantic_scholar
    uses ``doi`` / ``url`` plus ``paper_id``). This helper normalises
    them so ``_decide_existence`` can consume the result without knowing
    the source.
    """
    return {
        "title": hit.get("title") or "",
        "authors": list(hit.get("authors") or []),
        "year": hit.get("year"),
        "doi": hit.get("doi"),
        "canonical_url": hit.get("url") or hit.get("canonical_url"),
        "abstract": (hit.get("abstract") or "")[:800] if hit.get("abstract") else "",
    }


# ── Re8.1 Seed Repair capability functions ─────────────────────────────────
# Four capabilities required by WP2 Task 9:
#   1. Title similarity scoring (Jaccard + Levenshtein weighted)
#   2. Year conflict penalty (>2 years delta → decay)
#   3. Candidate confidence output (high/medium/low + ranking_reasons)
#   4. Conflict evidence preservation (dual-source retention)
#
# All four are pure functions with no side effects; they are consumed by
# ``_fetch_by_title`` to rank merged candidates and decorate the best
# one with confidence + ranking metadata. New fields are optional and
# do not affect ``_decide_existence`` or the public ``seed_resolver_node``
# contract — old callers see no behaviour change.

def _title_similarity(input_title: str, candidate_title: str) -> float:
    """Compute title similarity in [0.0, 1.0].

    Uses a weighted combination of token-based Jaccard similarity
    (0.6 weight) and character-level Levenshtein ratio via
    ``difflib.SequenceMatcher`` (0.4 weight). Both titles are first
    normalised (lowercase + strip punctuation + collapse whitespace).

    Boundary behaviour:
      - exact match after normalisation → 1.0
      - single-character typo            → typically >0.85
      - completely unrelated titles      → close to 0.0
      - either side empty                → 0.0
    """
    import re as _re
    from difflib import SequenceMatcher

    def _norm(s: str) -> str:
        return _re.sub(r"\s+", " ",
                       _re.sub(r"[^a-z0-9]+", " ", (s or "").lower())).strip()

    ni = _norm(input_title)
    nc = _norm(candidate_title)
    if not ni or not nc:
        return 0.0
    if ni == nc:
        return 1.0

    # Token Jaccard
    ti = set(ni.split())
    tc = set(nc.split())
    if not ti or not tc:
        jaccard = 0.0
    else:
        jaccard = len(ti & tc) / len(ti | tc)

    # Character-level ratio (Levenshtein-like, in [0,1])
    lev = SequenceMatcher(None, ni, nc).ratio()

    return 0.6 * jaccard + 0.4 * lev


def _year_penalty(input_year: int | None, candidate_year: int | None) -> float:
    """Return a year-based penalty coefficient in [0.3, 1.0].

    Rules (Re8.1 §2):
      - ``input_year`` is None       → 1.0 (cannot compare; no penalty)
      - ``candidate_year`` is None   → 0.7 (moderate penalty: unverifiable)
      - ``|delta| <= 2``             → 1.0 (consistent)
      - ``|delta| > 2``              → ``max(0.3, 1.0 - (delta - 2) * 0.1)``
                                       (linear decay, floor at 0.3)

    Returned value is a multiplier — multiply the candidate's raw score
    by this to apply the penalty.
    """
    if input_year is None:
        return 1.0
    if candidate_year is None:
        return 0.7
    try:
        delta = abs(int(input_year) - int(candidate_year))
    except (TypeError, ValueError):
        return 1.0
    if delta <= 2:
        return 1.0
    return max(0.3, 1.0 - (delta - 2) * 0.1)


def _compute_confidence(
    candidate: dict[str, Any],
    input_meta: dict[str, Any],
) -> tuple[str, list[str]]:
    """Compute ``(confidence_level, ranking_reasons)`` for a candidate.

    ``confidence_level`` ∈ {"high", "medium", "low"}.
    ``ranking_reasons`` is a list of short strings explaining which
    signals fired (e.g. ``"doi_match"``, ``"authors_full_match"``,
    ``"title_similarity_0.92"``, ``"year_consistent"``).

    Scoring (additive):
      - DOI present             → +0.4
      - Authors full match      → +0.3 / partial → +0.15 / none → +0
      - Title sim ≥ 0.9         → +0.2 / 0.7-0.9 → +0.1 / <0.7 → +0
      - Year consistent (≤2)    → +0.1

    Thresholds: ≥0.8 → high, 0.5-0.8 → medium, <0.5 → low.

    Author full match is defined as "every user-supplied surname is
    present in the candidate's surname set" — Crossref often lists more
    authors than the user, so a subset relation is more appropriate
    than strict set equality.
    """
    reasons: list[str] = []
    score = 0.0

    # DOI match
    cand_doi = (candidate.get("doi") or "").strip()
    if cand_doi:
        score += 0.4
        reasons.append("doi_match")

    # Author overlap (use normalised surnames for cross-source robustness)
    user_authors = [a for a in (input_meta.get("authors") or []) if a]
    cand_authors = [a for a in (candidate.get("authors") or []) if a]
    if user_authors and cand_authors:
        user_lastnames = {_author_lastname(a) for a in user_authors}
        cand_lastnames = {_author_lastname(a) for a in cand_authors}
        user_lastnames.discard("")
        cand_lastnames.discard("")
        if user_lastnames and user_lastnames <= cand_lastnames:
            score += 0.3
            reasons.append("authors_full_match")
        elif user_lastnames & cand_lastnames:
            score += 0.15
            reasons.append("authors_partial_match")

    # Title similarity
    input_title = input_meta.get("title") or ""
    cand_title = candidate.get("title") or ""
    if input_title and cand_title:
        sim = _title_similarity(input_title, cand_title)
        if sim >= 0.9:
            score += 0.2
            reasons.append(f"title_similarity_{sim:.2f}")
        elif sim >= 0.7:
            score += 0.1
            reasons.append(f"title_similarity_{sim:.2f}")
        else:
            # Still record the similarity for audit even when it
            # contributes 0 to the score.
            reasons.append(f"title_similarity_{sim:.2f}")

    # Year consistency
    input_year = input_meta.get("year")
    cand_year = candidate.get("year")
    if input_year is not None and cand_year is not None:
        try:
            iy = int(input_year)
            cy = int(cand_year)
            if abs(iy - cy) <= 2:
                score += 0.1
                reasons.append("year_consistent")
            else:
                reasons.append(f"year_conflict_delta_{abs(iy - cy)}")
        except (TypeError, ValueError):
            pass
    elif input_year is not None and cand_year is None:
        reasons.append("year_missing_on_candidate")

    if score >= 0.8:
        level = "high"
    elif score >= 0.5:
        level = "medium"
    else:
        level = "low"

    return level, reasons


def _merge_with_conflict_tagging(
    crossref_candidates: list[dict[str, Any]],
    s2_candidates: list[dict[str, Any]],
    *,
    input_title: str = "",
) -> list[dict[str, Any]]:
    """Merge Crossref + Semantic Scholar candidates with conflict tagging.

    Re8.1 §4 — preserve dual-source evidence; never silently drop a
    candidate just because the two sources disagree.

    Merge rules (in priority order):
      1. **DOI match across sources** — merge into one candidate,
         ``sources=["crossref", "semantic_scholar"]``, ``conflict=False``.
      2. **Title similarity ≥ 0.95 but DOI differs/missing** — keep
         BOTH candidates; each is tagged ``conflict=True`` and
         ``conflict_type="title_match_doi_mismatch"``. The downstream
         consumer can inspect the disagreement.
      3. **Single source only** — kept as-is with
         ``sources=[that_source]``, ``conflict=False``.

    The optional ``input_title`` is currently unused but accepted for
    future extension (e.g. biasing the title-similarity threshold based
    on how well the user's title matches either source).

    Each returned candidate is a new dict (input dicts are not mutated).
    """
    # Index Crossref candidates by DOI for join; those without DOI go
    # to a separate list for the title-match conflict pass.
    crossref_by_doi: dict[str, dict[str, Any]] = {}
    crossref_no_doi: list[dict[str, Any]] = []
    for c in crossref_candidates:
        c = dict(c)
        c.setdefault("sources", ["crossref"])
        c.setdefault("conflict", False)
        doi = (c.get("doi") or "").strip().lower()
        if doi:
            crossref_by_doi[doi] = c
        else:
            crossref_no_doi.append(c)

    s2_by_doi: dict[str, dict[str, Any]] = {}
    s2_no_doi: list[dict[str, Any]] = []
    for c in s2_candidates:
        c = dict(c)
        c.setdefault("sources", ["semantic_scholar"])
        c.setdefault("conflict", False)
        doi = (c.get("doi") or "").strip().lower()
        if doi:
            s2_by_doi[doi] = c
        else:
            s2_no_doi.append(c)

    merged: list[dict[str, Any]] = []

    # 1. DOI-matched: merge crossref + s2 into one candidate
    matched_s2_dois: set[str] = set()
    for doi, cr in crossref_by_doi.items():
        if doi in s2_by_doi:
            s2 = s2_by_doi[doi]
            merged_item = dict(cr)
            # Crossref fields win; s2 fills gaps only.
            for k, v in s2.items():
                if k in ("sources", "conflict"):
                    continue
                if not merged_item.get(k):
                    merged_item[k] = v
            merged_item["sources"] = ["crossref", "semantic_scholar"]
            merged_item["conflict"] = False
            merged.append(merged_item)
            matched_s2_dois.add(doi)
        else:
            merged.append(cr)

    # 2. s2-only DOI candidates (no Crossref match)
    for doi, s2 in s2_by_doi.items():
        if doi not in matched_s2_dois:
            merged.append(s2)

    # 3. Crossref no-DOI candidates: check for title-match conflict with
    #    s2 no-DOI candidates. If titles agree (sim ≥ 0.95), keep BOTH
    #    and tag as conflict; otherwise keep as single-source.
    used_s2_no_doi: set[int] = set()
    for cr in crossref_no_doi:
        cr_title = cr.get("title") or ""
        matched = False
        for idx, s2 in enumerate(s2_no_doi):
            if idx in used_s2_no_doi:
                continue
            s2_title = s2.get("title") or ""
            if cr_title and s2_title:
                sim = _title_similarity(cr_title, s2_title)
                if sim >= 0.95:
                    cr["conflict"] = True
                    cr["conflict_type"] = "title_match_doi_mismatch"
                    s2["conflict"] = True
                    s2["conflict_type"] = "title_match_doi_mismatch"
                    merged.append(cr)
                    merged.append(s2)
                    used_s2_no_doi.add(idx)
                    matched = True
                    break
        if not matched:
            merged.append(cr)

    # 4. s2-only no-DOI candidates not consumed by conflict matching
    for idx, s2 in enumerate(s2_no_doi):
        if idx not in used_s2_no_doi:
            merged.append(s2)

    return merged


async def _fetch_by_title(
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
) -> dict[str, Any] | None:
    """Search Crossref + Semantic Scholar by title in parallel.

    Returns the best-matching candidate (normalised to the
    ``_decide_existence`` schema) or ``None`` when no candidate's title
    agrees with the query.

    Used by ``_resolve_one_seed`` when ``input_form == "title"`` and no
    stable identifier is available. Previously such seeds were marked
    ``ambiguous`` without any network attempt (Seed Repair空转, Re8.0
    second batch). This function performs the actual cross-source title
    search and selects the strongest candidate by DOI presence + author
    overlap.

    Re8.1 (WP2 Task 9): now uses title-similarity scoring, year-penalty,
    confidence computation, and dual-source conflict tagging. The
    returned dict carries optional ``confidence``, ``ranking_reasons``,
    ``sources``, ``conflict``, ``conflict_type`` and ``all_candidates``
    fields — these are informational and do not affect
    ``_decide_existence`` behaviour. Old callers see no API change
    (``year`` is an optional kwarg defaulting to None).

    The ``all_candidates`` field preserves every merged candidate so
    downstream consumers can inspect the conflict evidence; it is never
    empty when the function returns non-None.
    """
    from apps.api.app.services.retrieval.adapters.crossref_search import crossref_search
    from apps.api.app.services.retrieval.adapters.semantic_scholar_search import (
        semantic_scholar_search,
    )

    try:
        crossref_hits, s2_hits = await asyncio.gather(
            crossref_search([title], top_k=5),
            semantic_scholar_search([title], top_k=5),
            return_exceptions=True,
        )
    except Exception as exc:
        logger.debug("title search gather failed for %s: %s", title, exc)
        return None

    # gather with return_exceptions=True returns Exception objects on failure
    if isinstance(crossref_hits, Exception):
        logger.debug("crossref title search failed: %s", crossref_hits)
        crossref_hits = []
    if isinstance(s2_hits, Exception):
        logger.debug("semantic_scholar title search failed: %s", s2_hits)
        s2_hits = []

    # Pre-filter via _titles_agree (loose substring match) to avoid
    # promoting clearly-unrelated hits. Re8.0 behaviour preserved.
    crossref_candidates: list[dict[str, Any]] = []
    for hit in (crossref_hits or []):
        if isinstance(hit, dict) and _titles_agree(title, hit.get("title", "")):
            cand = _normalize_title_hit(hit, "crossref")
            cand["sources"] = ["crossref"]
            cand["conflict"] = False
            crossref_candidates.append(cand)
    s2_candidates: list[dict[str, Any]] = []
    for hit in (s2_hits or []):
        if isinstance(hit, dict) and _titles_agree(title, hit.get("title", "")):
            cand = _normalize_title_hit(hit, "semantic_scholar")
            cand["sources"] = ["semantic_scholar"]
            cand["conflict"] = False
            s2_candidates.append(cand)

    # Re8.1 §4: merge with conflict tagging (preserves dual-source evidence)
    merged = _merge_with_conflict_tagging(
        crossref_candidates, s2_candidates, input_title=title,
    )

    if not merged:
        return None

    # Re8.1 §1-3: decorate every candidate with confidence + ranking_reasons
    # and rank by a composite score that blends confidence anchor,
    # title similarity, and year penalty.
    input_meta = {
        "title": title,
        "authors": list(authors or []),
        "year": year,
    }

    confidence_anchor = {"high": 0.8, "medium": 0.55, "low": 0.25}

    scored: list[tuple[dict[str, Any], float]] = []
    for cand in merged:
        level, reasons = _compute_confidence(cand, input_meta)
        cand["confidence"] = level
        cand["ranking_reasons"] = reasons
        sim = _title_similarity(title, cand.get("title") or "")
        penalty = _year_penalty(year, cand.get("year"))
        # Composite score: confidence anchor dominates, but similarity
        # and year penalty can break ties and demote conflict candidates.
        score = confidence_anchor[level] * 0.6 + sim * 0.3 + penalty * 0.1
        # Mild penalty for conflict-tagged candidates so a clean
        # single-source match wins over a conflicting dual-source one
        # when scores are otherwise close.
        if cand.get("conflict"):
            score -= 0.05
        scored.append((cand, score))

    scored.sort(key=lambda t: t[1], reverse=True)
    best = dict(scored[0][0])
    # Preserve the full merged list for downstream inspection. Each
    # candidate in this list already has confidence + ranking_reasons
    # + sources + conflict fields populated.
    best["all_candidates"] = [c for c, _ in scored]
    return best


# ── Re8.2 WP2 — Seed Repair 2.0: title normalisation ───────────────────────

import unicodedata

_ACRONYM_MAP: dict[str, str] = {
    # Common ML/DL paper acronyms: full name → alias
    "bidirectional encoder representations from transformers": "bert",
    "generative pre-trained transformer": "gpt",
    "vision transformer": "vit",
    "convolutional neural network": "cnn",
    "deep residual learning": "resnet",
    "you only look once": "yolo",
    "generative adversarial network": "gan",
    "masked autoencoder": "mae",
    "contrastive language-image pre-training": "clip",
    "denoising diffusion probabilistic model": "ddpm",
    "cross-lingual language model": "xlm",
    "robustly optimized bert approach": "roberta",
    "knowledge graph": "kg",
    "long short-term memory": "lstm",
    "graph neural network": "gnn",
    "reinforcement learning": "rl",
    "natural language processing": "nlp",
    "mixture of experts": "moe",
    "convolutional lstm": "convlstm",
    "latent diffusion model": "ldm",
    "hidden markov model": "hmm",
    "support vector machine": "svm",
    "conditional random field": "crf",
    "multi-layer perceptron": "mlp",
    "recurrent neural network": "rnn",
    "variational autoencoder": "vae",
    "principal component analysis": "pca",
    "independent component analysis": "ica",
    "node2vec": "node2vec",
    "word2vec": "word2vec",
    "deeplab": "deeplab",
    "u-net": "unet",
    "temporal convolutional network": "tcn",
    "fully convolutional network": "fcn",
    "deep q-network": "dqn",
    "auto-encoding variational bayes": "aevb",
    "neural architecture search": "nas",
    "gradient boosting machine": "gbm",
    "extreme gradient boosting": "xgboost",
    "random forest": "rf",
    "graph attention network": "gat",
    "graph convolutional network": "gcn",
}


def _normalize_title_for_query(title: str) -> str:
    """Normalize a title string for query matching (Re8.2 WP2).

    Steps:
      1. Unicode NFC normalize
      2. Lowercase
      3. Strip leading/trailing whitespace
      4. Collapse all whitespace runs to single space

    Used as the base normalisation for all query variants.
    """
    t = unicodedata.normalize("NFC", title)
    t = t.lower().strip()
    import re as _re2
    t = _re2.sub(r"\s+", " ", t)
    return t


def _strip_subtitle(title: str) -> str:
    """Remove subtitle after colon or em-dash, return the main title.

    E.g. ``"BERT: Pre-training of Deep Bidirectional Transformers"``
    → ``"bert pre training of deep bidirectional transformers"``
    """
    t = _normalize_title_for_query(title)
    import re as _re2
    # Split on colon or em-dash (but keep if no separator)
    for sep in (r"\s*—\s*", r"\s*–\s*", r"\s*:\s*"):
        parts = _re2.split(sep, t, maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            return parts[0].strip()
    return t


def _remove_punctuation(title: str) -> str:
    """Remove common punctuation from a normalized title."""
    import re as _re2
    return _re2.sub(r"[^\w\s]", "", title)


def _extract_core_terms(title: str, max_terms: int = 5) -> list[str]:
    """Extract the most significant terms from a title.

    Strips stopwords and short tokens, returns at most ``max_terms``
    tokens. Used for the author+core and year+core query variants.
    """
    import re as _re2
    _STOPWORDS: set[str] = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can", "need",
        "dare", "ought", "used", "this", "that", "these", "those", "it",
        "its", "they", "them", "their", "we", "our", "you", "your", "he",
        "she", "his", "her", "him", "i", "me", "my", "mine",
        "not", "no", "nor", "neither", "so", "very", "just", "about",
        "over", "under", "above", "below", "between", "through", "during",
        "before", "after", "up", "down", "out", "off", "than", "then",
        "also", "too", "only", "well", "even", "still", "already", "yet",
        "because", "since", "while", "although", "though", "if", "unless",
        "until", "once", "after", "before",
        "via", "per", "into", "onto", "upon", "within", "without",
        "more", "most", "much", "many", "some", "any", "each", "every",
        "both", "all", "few", "several", "such", "like",
        "how", "what", "which", "who", "whom", "whose", "where", "when",
        "why", "whether",
        "toward", "towards", "among", "amongst", "between",
        "one", "two", "three", "first", "second", "new", "novel",
    }
    t = _normalize_title_for_query(title)
    t = _remove_punctuation(t)
    tokens = [w for w in t.split() if len(w) > 2 and w not in _STOPWORDS]
    # Return unique tokens, up to max_terms, preserving order
    seen: set[str] = set()
    result: list[str] = []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            result.append(tok)
            if len(result) >= max_terms:
                break
    return result


def _generate_acronym_aliases(title: str) -> list[str]:
    """Generate acronym aliases for a title.

    Checks if the normalized title matches any known full name in
    ``_ACRONYM_MAP`` and returns the alias(es). Also tries to
    generate an acronym from the first letter of each word.
    """
    t = _normalize_title_for_query(title)
    aliases: list[str] = []
    for full_name, alias in _ACRONYM_MAP.items():
        if full_name in t:
            aliases.append(alias)
    # Also try word-initial acronym generation for >=3 word titles
    words = t.split()
    if len(words) >= 3:
        acronym = "".join(w[0] for w in words if w and w[0].isalpha())
        if acronym and acronym not in aliases:
            aliases.append(acronym)
    return aliases


def _build_query_variants(
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
) -> list[str]:
    """Build up to 4 query variants for multi-strategy search (Re8.2 WP2).

    Strategies:
      1. Full original title (as-is, for exact-match APIs)
      2. Subtitle-stripped title (remove after colon/dash)
      3. Author last name + core terms (if authors available)
      4. Year + core terms (if year available)

    Returns a list of query strings (1-4 entries). Empty or duplicate
    entries are filtered out.
    """
    queries: list[str] = []
    # S1: full original title
    full = title.strip()
    if full:
        queries.append(full)
    # S2: subtitle-stripped
    stripped = _strip_subtitle(title)
    if stripped and stripped != _normalize_title_for_query(full):
        queries.append(stripped)
    # S3: author + core terms
    core = _extract_core_terms(title)
    if authors and core:
        author_part = " ".join(
            _author_lastname(a) for a in authors if _author_lastname(a)
        )
        if author_part:
            queries.append(f"{author_part} {' '.join(core)}")
    # S4: year + core terms
    if year is not None and core:
        queries.append(f"{year} {' '.join(core)}")
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        nq = _normalize_title_for_query(q)
        if nq and nq not in seen:
            seen.add(nq)
            unique.append(q)
    return unique


# ── Re8.2 WP2 — Seed Repair 2.0: multi-source parallel fetch ───────────────


def _openalex_result_to_candidate(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an OpenAlex search result to a partial SeedCandidate dict."""
    title = raw.get("title") or ""
    if not title:
        return None
    authors_list: list[str] = []
    for a in (raw.get("authorships") or []):
        if isinstance(a, dict):
            n = a.get("author", {}).get("display_name") if isinstance(a.get("author"), dict) else None
            if n:
                authors_list.append(n)
    doi = raw.get("doi") or ""
    if doi and isinstance(doi, str):
        doi = doi.replace("https://doi.org/", "")
    arxiv_id = None
    for loc in (raw.get("locations") or []):
        if isinstance(loc, dict):
            lp = loc.get("landing_page_url") or ""
            if "arxiv.org" in lp:
                m = _ARXIV_URL_RE.search(lp)
                if m:
                    arxiv_id = m.group(1)
    return {
        "title": title,
        "authors": authors_list,
        "year": raw.get("publication_year"),
        "doi": doi or None,
        "arxiv_id": arxiv_id,
        "canonical_url": raw.get("id") or "",
        "abstract": raw.get("abstract") or "",
        "venue": "",
        "sources": ["openalex"],
    }


def _arxiv_result_to_candidate(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an arXiv search result to a partial SeedCandidate dict."""
    title = raw.get("title") or ""
    if not title:
        return None
    return {
        "title": title,
        "authors": list(raw.get("authors") or []),
        "year": raw.get("year"),
        "doi": raw.get("doi"),
        "arxiv_id": raw.get("arxiv_id"),
        "canonical_url": raw.get("url") or "",
        "abstract": raw.get("abstract") or "",
        "venue": "",
        "sources": ["arxiv"],
    }


def _source_result_to_candidate(source: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatch source-specific normalisation to a partial SeedCandidate dict.

    ``raw`` is a single hit dict from any supported source. Returns None
    when the hit is unusable (empty title).
    """
    if source == "openalex":
        return _openalex_result_to_candidate(raw)
    if source == "arxiv":
        return _arxiv_result_to_candidate(raw)
    # Crossref and Semantic Scholar share the same normalisation path
    title = raw.get("title") or ""
    if not title:
        return None
    return {
        "title": title,
        "authors": list(raw.get("authors") or []),
        "year": raw.get("year"),
        "doi": raw.get("doi"),
        "arxiv_id": raw.get("arxiv_id"),
        "canonical_url": raw.get("url") or raw.get("canonical_url") or "",
        "abstract": raw.get("abstract") or "",
        "venue": raw.get("venue") or "",
        "sources": [source],
    }


def _deduplicate_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate candidates by DOI (preferred) then by normalised title.

    When two candidates share a DOI, the one with more sources wins
    (sources merged). When two candidates share a title (after
    normalisation) but no DOI, they are kept as separate entries but
    tagged with a conflict marker.
    """
    doi_map: dict[str, dict[str, Any]] = {}
    title_clusters: list[list[dict[str, Any]]] = []
    title_index: dict[str, int] = {}

    for c in candidates:
        doi = (c.get("doi") or "").strip().lower()
        if doi:
            if doi in doi_map:
                existing = doi_map[doi]
                existing_sources = set(existing.get("sources") or [])
                new_sources = set(c.get("sources") or [])
                existing["sources"] = sorted(existing_sources | new_sources)
                # Merge authors from both sources while preserving order
                existing_authors = list(existing.get("authors") or [])
                new_authors = list(c.get("authors") or [])
                seen_authors: set[str] = set(a.lower().strip() for a in existing_authors)
                merged_authors = list(existing_authors)
                for a in new_authors:
                    key = a.lower().strip()
                    if key and key not in seen_authors:
                        seen_authors.add(key)
                        merged_authors.append(a)
                existing["authors"] = merged_authors
                # Fill gaps: prefer existing values, fill from new
                for k in ("title", "year", "arxiv_id", "canonical_url", "abstract"):
                    if not existing.get(k) and c.get(k):
                        existing[k] = c[k]
            else:
                doi_map[doi] = dict(c)
        else:
            # No DOI: cluster by normalised title
            import re as _re2
            nt = _re2.sub(r"[^a-z0-9]+", " ", (c.get("title") or "").lower()).strip()
            if nt in title_index:
                title_clusters[title_index[nt]].append(c)
            else:
                title_index[nt] = len(title_clusters)
                title_clusters.append([c])

    result: list[dict[str, Any]] = list(doi_map.values())
    for cluster in title_clusters:
        if len(cluster) == 1:
            result.append(cluster[0])
        else:
            # Multiple candidates with same normalised title but no DOI
            # → keep all with conflict marker
            for c in cluster:
                c["conflict"] = True
                c.setdefault("sources", [])
                result.append(c)

    return result


def _normalize_candidate_title(title: str) -> str:
    """Fully normalize a candidate title for comparison (Re8.2 WP2).

    Includes: Unicode NFC, lowercase, punctuation removal, whitespace
    collapse. Used as the comparison key for scoring.
    """
    t = unicodedata.normalize("NFC", title)
    t = t.lower()
    import re as _re2
    t = _re2.sub(r"[^\w\s]", "", t)
    t = _re2.sub(r"\s+", " ", t).strip()
    return t


def _compute_structured_scores(
    input_title: str,
    input_authors: list[str],
    input_year: int | None,
    candidate: dict[str, Any],
) -> dict[str, float]:
    """Compute structured per-component scores for a candidate (Re8.2 WP2).

    Scoring formula (Plan A):
      total = 0.35*title + 0.25*author + 0.15*year + 0.15*abstract + 0.10*identifier

    Each component score is in [0.0, 1.0].

    Plan B conservative logic (caller applies via ``_apply_threshold``):
      (title >= 0.88 AND author >= 0.70) OR identifier == 1.0

    Returns a dict with keys: title_score, author_score, year_score,
    abstract_score, identifier_score.
    """
    # ── Title score ────────────────────────────────────────────────────
    cand_title = candidate.get("title") or ""
    if input_title and cand_title:
        title_score = _title_similarity(input_title, cand_title)
    else:
        title_score = 0.0

    # ── Author score (Jaccard on normalised last names) ────────────────
    user_lastnames = {_author_lastname(a) for a in input_authors if a}
    user_lastnames.discard("")
    cand_lastnames = {_author_lastname(a) for a in (candidate.get("authors") or []) if a}
    cand_lastnames.discard("")
    if user_lastnames and cand_lastnames:
        intersection = user_lastnames & cand_lastnames
        author_score = len(intersection) / len(user_lastnames | cand_lastnames)
    elif not user_lastnames and not cand_lastnames:
        author_score = 0.5  # neutral when both absent
    else:
        author_score = 0.0  # one side has authors, other doesn't

    # ── Year score ─────────────────────────────────────────────────────
    cand_year = candidate.get("year")
    if input_year is not None and cand_year is not None:
        try:
            delta = abs(int(input_year) - int(cand_year))
            if delta <= 1:
                year_score = 1.0
            elif delta <= 3:
                year_score = 0.7
            elif delta <= 5:
                year_score = 0.4
            else:
                year_score = 0.1
        except (TypeError, ValueError):
            year_score = 0.5
    elif input_year is None and cand_year is None:
        year_score = 0.5  # neutral when both absent
    elif input_year is not None and cand_year is None:
        year_score = 0.3  # candidate has no year — penalty
    else:
        year_score = 0.3  # input has no year — penalty

    # ── Abstract score ─────────────────────────────────────────────────
    input_abstract = ""  # not passed to _fetch_by_title currently
    cand_abstract = candidate.get("abstract") or ""
    if input_abstract and cand_abstract:
        ia_tokens = set(_normalize_candidate_title(input_abstract).split())
        ca_tokens = set(_normalize_candidate_title(cand_abstract).split())
        if ia_tokens and ca_tokens:
            abstract_score = len(ia_tokens & ca_tokens) / len(ia_tokens | ca_tokens)
        else:
            abstract_score = 0.0
    elif cand_abstract:
        # Candidate has abstract but input doesn't → partial credit
        abstract_score = 0.3
    else:
        abstract_score = 0.0

    # ── Identifier score ───────────────────────────────────────────────
    doi = (candidate.get("doi") or "").strip()
    arxiv = (candidate.get("arxiv_id") or "").strip()
    if doi and _DOI_RE.search(doi):
        identifier_score = 1.0
    elif arxiv:
        identifier_score = 0.8
    else:
        identifier_score = 0.0

    return {
        "title_score": round(title_score, 4),
        "author_score": round(author_score, 4),
        "year_score": round(year_score, 4),
        "abstract_score": round(abstract_score, 4),
        "identifier_score": round(identifier_score, 4),
    }


def _apply_threshold(
    scores: dict[str, float],
    *,
    use_plan_b: bool = False,
) -> tuple[str, float]:
    """Apply structured scoring threshold and return (confidence, total_score).

    Plan A (default):
      total = 0.35*title + 0.25*author + 0.15*year + 0.15*abstract + 0.10*identifier
      >= 0.85  → "verified"
      0.70-0.85 → "ambiguous"
      < 0.70   → "not_found"

    Plan B (conservative):
      (title >= 0.88 AND author >= 0.70) OR identifier == 1.0 → "verified"
      Otherwise fall back to Plan A thresholds.
    """
    from apps.api.app.services.agents.graph.re80_schema import (
        SEED_AMBIGUOUS_LOWER,
        SEED_VERIFIED_THRESHOLD,
    )

    total = (
        0.35 * scores["title_score"]
        + 0.25 * scores["author_score"]
        + 0.15 * scores["year_score"]
        + 0.15 * scores["abstract_score"]
        + 0.10 * scores["identifier_score"]
    )
    total = round(total, 4)

    if use_plan_b:
        title_ok = scores["title_score"] >= 0.88
        author_ok = scores["author_score"] >= 0.70
        identifier_ok = scores["identifier_score"] >= 1.0
        if (title_ok and author_ok) or identifier_ok:
            confidence = "verified"
        elif total >= SEED_VERIFIED_THRESHOLD:
            # Override to ambiguous if Plan B would not verify
            confidence = "ambiguous"
        elif total >= SEED_AMBIGUOUS_LOWER:
            confidence = "ambiguous"
        else:
            confidence = "not_found"
    else:
        if total >= SEED_VERIFIED_THRESHOLD:
            confidence = "verified"
        elif total >= SEED_AMBIGUOUS_LOWER:
            confidence = "ambiguous"
        else:
            confidence = "not_found"

    return confidence, total


def _resolve_confidence_to_string(confidence: str) -> str:
    """Map threshold confidence to a human-readable level string.

    "verified" → "high", "ambiguous" → "medium", "not_found" → "low".
    """
    return {"verified": "high", "ambiguous": "medium", "not_found": "low"}.get(
        confidence, "low"
    )


# ── Re8.2 WP2 — Seed Repair 2.0: LLM disambiguation ────────────────────────


def _should_llm_disambiguate(candidates: list[dict[str, Any]]) -> bool:
    """Determine whether LLM disambiguation is warranted (Re8.2 WP2).

    Conditions (ALL must hold):
      1. 2 <= n_candidates <= 5
      2. Top-1 and Top-2 total_score gap < 0.08
      3. At least one candidate has confidence >= "ambiguous" (total >= 0.70)
    """
    if len(candidates) < 2 or len(candidates) > 5:
        return False
    scored = sorted(candidates, key=lambda c: c.get("total_score", 0.0), reverse=True)
    gap = scored[0].get("total_score", 0.0) - scored[1].get("total_score", 0.0)
    if gap >= 0.08:
        return False
    has_min = any(c.get("total_score", 0.0) >= 0.70 for c in scored)
    return has_min


async def _llm_disambiguate(
    input_title: str,
    input_authors: list[str],
    input_year: int | None,
    candidates: list[dict[str, Any]],
    *,
    profile: str = "premium_review",
) -> dict[str, Any]:
    """LLM disambiguation for close-score candidates (Re8.2 WP2).

    The LLM receives the original user input (title, authors, year) plus
    the list of candidates with their structured scores. It can only:
      - Select one existing candidate by index (0-based)
      - Reject all (``reject_all``)

    The LLM MUST NOT retrieve, create, or hallucinate new candidates.

    Returns the selected candidate dict (with ``_disambiguation`` marker)
    or None when all are rejected.
    """
    import json as _json

    prompt_lines = [
        "[DISAMBIGUATION] You are a seed paper disambiguator.",
        "",
        "User input:",
        f"  Title:   {input_title}",
        f"  Authors: {', '.join(input_authors) if input_authors else '(none)'}",
        f"  Year:    {input_year if input_year is not None else '(unknown)'}",
        "",
        "Candidates (scored by structural similarity):",
    ]
    for i, c in enumerate(candidates):
        prompt_lines.append(f"  [{i}] title={c.get('title','')}")
        prompt_lines.append(f"      authors={', '.join(c.get('authors') or [])}")
        prompt_lines.append(f"      year={c.get('year')}, doi={c.get('doi') or 'N/A'}")
        prompt_lines.append(f"      total_score={c.get('total_score', 0.0)}")
        prompt_lines.append(f"      confidence={c.get('confidence', 'not_found')}")
        prompt_lines.append("")

    prompt_lines.append(
        "Your task: select the candidate that matches the user input best,"
    )
    prompt_lines.append("or reject all if none match.")
    prompt_lines.append("")
    prompt_lines.append(
        "IMPORTANT: You may ONLY choose from the candidates listed above."
    )
    prompt_lines.append(
        "Do NOT retrieve, create, or hallucinate new candidates."
    )
    prompt_lines.append("")
    prompt_lines.append("Output JSON:")
    prompt_lines.append(
        '{"selected_index": <int|null>, "confidence": "high|medium|low", '
        '"reason": "<str>", "reject_all": <bool>}'
    )
    prompt_lines.append(
        "  selected_index=0 → candidates[0]; selected_index=null or "
        "reject_all=true → reject all."
    )
    prompt_lines.append(
        "  confidence=high/medium/low expresses your certainty. "
        "Only high confidence should lead to verification."
    )
    prompt_lines.append("")
    prompt_lines.append(
        "[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."
    )

    prompt = "\n".join(prompt_lines)

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system="You are a seed paper disambiguator. Select the best matching candidate or reject all.",
            node_name="seed_disambiguator",
            profile=profile,
            contract_id="seed-disambiguation/v1",
            max_tokens=400,
            timeout=20.0,
            fallback=None,
        )
    except Exception as exc:
        logger.warning("seed disambiguation LLM call failed: %s — reject_all", exc)
        return None

    if not isinstance(raw, dict):
        return None

    # SOP format: reject_all / confidence / selected_index / reason
    # Backward compat: selection / rationale
    if raw.get("reject_all") is True:
        return None

    llm_confidence = str(raw.get("confidence", "")).strip().lower()
    if llm_confidence == "low":
        return None

    selected_index = raw.get("selected_index")
    if selected_index is None or selected_index == "null":
        # Backward-compatible fallback to legacy "selection" field
        selected_index = raw.get("selection")
    if selected_index is None or selected_index == "null":
        return None

    try:
        idx = int(selected_index)
    except (TypeError, ValueError):
        idx = -1

    if idx < 0 or idx >= len(candidates):
        return None

    selected = dict(candidates[idx])
    selected["_disambiguation"] = {
        "selected_index": idx,
        "reason": str(raw.get("reason", raw.get("rationale", ""))),
        "llm_confidence": llm_confidence or "unspecified",
        "n_candidates": len(candidates),
    }
    return selected


# ── Re8.2 WP2 — Seed Repair 2.0: orchestrator ──────────────────────────────


async def _fetch_seed_candidates(
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
    *,
    profile: str = "premium_review",
) -> dict[str, Any] | None:
    """Multi-source parallel seed search with structured scoring (Re8.2 WP2).

    Builds up to 4 query variants (full title, stripped, author+core,
    year+core) and dispatches them to Crossref, Semantic Scholar,
    OpenAlex, and arXiv in parallel via ``asyncio.gather``.

    Each source result is normalised to a partial SeedCandidate dict,
    deduplicated, and scored via ``_compute_structured_scores`` with
    Plan A formula and Plan B conservative check.

    When the top candidates are close (gap < 0.08, 2-5 candidates,
    at least one >= 0.70), an optional LLM disambiguation step is
    triggered to select the best match or reject all.

    Returns the best candidate decorated with scores, or None when
    no candidate meets the minimum threshold.

    All fields on the returned dict are additive; existing callers
    that expect the ``_fetch_by_title`` shape still work.
    """
    from apps.api.app.services.retrieval.adapters.crossref_search import crossref_search
    from apps.api.app.services.retrieval.adapters.semantic_scholar_search import (
        semantic_scholar_search,
    )
    from apps.api.app.services.retrieval.adapters.openalex_search import openalex_search
    from apps.api.app.services.retrieval.adapters.arxiv_search import arxiv_search

    if not title or not title.strip():
        return None

    input_authors = list(authors or [])
    input_year = year

    # ── 1. Build query variants ────────────────────────────────────────
    queries = _build_query_variants(title, authors=input_authors, year=input_year)
    if not queries:
        return None

    # ── 2. Parallel search across all sources ──────────────────────────
    crossref_tasks = [crossref_search([q], top_k=5) for q in queries]
    s2_tasks = [semantic_scholar_search([q], top_k=5) for q in queries]
    oa_tasks = [openalex_search([q], top_k=5) for q in queries]
    arxiv_tasks = [arxiv_search([q], top_k=5) for q in queries]

    all_raw: list[list[Any]] = [[], [], [], []]  # crossref, s2, oa, arxiv

    try:
        results = await asyncio.gather(
            asyncio.gather(*crossref_tasks, return_exceptions=True),
            asyncio.gather(*s2_tasks, return_exceptions=True),
            asyncio.gather(*oa_tasks, return_exceptions=True),
            asyncio.gather(*arxiv_tasks, return_exceptions=True),
            return_exceptions=True,
        )
    except Exception as exc:
        logger.debug("seed_candidates gather failed for %s: %s", title, exc)
        return None

    # Unpack results (nested gather)
    if not isinstance(results, (list, tuple)) or len(results) != 4:
        return None

    for source_idx, source_results in enumerate(results):
        if isinstance(source_results, Exception):
            logger.debug("seed_candidates source %d failed: %s", source_idx, source_results)
            continue
        for query_results in source_results:
            if isinstance(query_results, Exception):
                continue
            if isinstance(query_results, list):
                all_raw[source_idx].extend(query_results)

    source_names = ["crossref", "semantic_scholar", "openalex", "arxiv"]

    # ── 3. Normalize results to partial SeedCandidate dicts ────────────
    raw_candidates: list[dict[str, Any]] = []
    for source_idx, items in enumerate(all_raw):
        source = source_names[source_idx]
        for item in items:
            if not isinstance(item, dict):
                continue
            cand = _source_result_to_candidate(source, item)
            if cand is not None:
                raw_candidates.append(cand)

    if not raw_candidates:
        return None

    # ── 4. Deduplicate ─────────────────────────────────────────────────
    candidates = _deduplicate_candidates(raw_candidates)

    # ── 5. Compute structured scores for each candidate ────────────────
    for c in candidates:
        scores = _compute_structured_scores(title, input_authors, input_year, c)
        c.update(scores)
        confidence, total = _apply_threshold(scores, use_plan_b=False)
        c["confidence"] = confidence
        c["total_score"] = total
        # Also compute Plan B for auditing
        plan_b_conf, _ = _apply_threshold(scores, use_plan_b=True)
        c["confidence_plan_b"] = plan_b_conf

    # ── 6. Sort by total_score descending ──────────────────────────────
    candidates.sort(key=lambda c: c.get("total_score", 0.0), reverse=True)

    # ── 7. LLM disambiguation (when conditions warrant) ────────────────
    if _should_llm_disambiguate(candidates):
        llm_selected = await _llm_disambiguate(
            title, input_authors, input_year, candidates, profile=profile,
        )
        if llm_selected is not None:
            # LLM selected a candidate → use it, but verify confidence
            if llm_selected.get("confidence") != "verified":
                # LLM selection but low confidence → ambiguous
                llm_selected["confidence"] = "ambiguous"
                llm_selected["_llm_override"] = "low_confidence_downgrade"
            # Promote the original candidate object to the top so that
            # list.remove() does not fail because of added metadata.
            idx = llm_selected.get("_disambiguation", {}).get("selected_index")
            if isinstance(idx, int) and 0 <= idx < len(candidates):
                selected = candidates.pop(idx)
                selected["confidence"] = llm_selected["confidence"]
                selected["_disambiguation"] = llm_selected["_disambiguation"]
                if "_llm_override" in llm_selected:
                    selected["_llm_override"] = llm_selected["_llm_override"]
                candidates.insert(0, selected)
            else:
                candidates.insert(0, llm_selected)
        # else: LLM rejected all → keep current ranking, no verified

    # ── 8. Return best candidate if score >= ambiguous threshold ───────
    best = candidates[0]
    if best.get("total_score", 0.0) < 0.70 and best.get("confidence") == "not_found":
        return None

    # Preserve all candidates for downstream inspection
    best["all_candidates"] = candidates
    return best


# ── Per-seed resolution ─────────────────────────────────────────────────────

def _status_from_fetched(
    flat: dict[str, Any],
    fetched: dict[str, Any] | None,
) -> tuple[str, str | None]:
    """Map a fetched/searched candidate to an existence_status + repair_hint.

    Re8.2 WP2 structured-scoring path uses ``total_score`` and
    ``confidence`` in {"verified", "ambiguous", "not_found"}. The legacy
    Re8.1 ``_fetch_by_title`` path uses ``confidence`` in
    {"high", "medium", "low"} and falls back to ``_decide_existence``.
    """
    if fetched is None:
        title = (flat.get("title") or "").strip()
        if title:
            return "ambiguous", "no authoritative landing page; consider Repair via author/year"
        return "not_found", "no identifier and no title; cannot verify"

    wp2_total = fetched.get("total_score")
    if wp2_total is not None:
        wp2_confidence = fetched.get("confidence", "ambiguous")
        if wp2_confidence == "verified":
            return "verified", None
        if wp2_confidence == "ambiguous":
            return "ambiguous", "seed repair: structured score in ambiguous range"
        return "ambiguous", "seed repair: low confidence match"

    return _decide_existence(flat, fetched)


async def _resolve_one_seed(
    seed_id: str,
    payload: dict[str, Any],
    *,
    offline: bool = False,
) -> dict[str, Any]:
    """Resolve a single candidate seed into a SeedPaperCard.

    When ``offline`` is True (network_policy == "offline"), we skip all
    network fetches and mark the card as ``ambiguous`` with a note. This
    keeps Offline Replay mode hermetic (Re8.0 §8.4).
    """
    # Flatten raw_input onto top-level so identifier / metadata fields
    # nested by the demo or API callers are visible to classification
    # and card construction (Re8.0 P0-1). The original ``payload`` is
    # preserved as ``raw_input`` on the emitted card for audit.
    flat = _normalize_seed_payload(payload)
    input_form, identifier = _classify_input(flat)
    if input_form not in SEED_INPUT_FORMS:
        input_form = "citation"

    # Local PDF path: no network needed, mark as verified-local
    if input_form == "pdf":
        card = make_seed_card(
            seed_id=seed_id,
            input_form="pdf",
            resolved_title=flat.get("title"),
            existence_status="verified",
            fulltext_status="metadata_only",
            role=flat.get("role", "unknown"),
            raw_input=dict(payload),  # preserve pdf_bytes for paper_understanding
        )
        card["repair_hint"] = "local PDF; fulltext parse pending (WP2)"
        return card

    if offline:
        # Offline mode — no network fetches, keep as ambiguous
        card = make_seed_card(
            seed_id=seed_id,
            input_form=input_form,
            resolved_title=flat.get("title"),
            authors=list(flat.get("authors") or []),
            year=flat.get("year"),
            doi=flat.get("doi"),
            canonical_url=flat.get("url"),
            existence_status="ambiguous",
            fulltext_status="metadata_only",
            role=flat.get("role", "unknown"),
            raw_input=payload,
        )
        card["repair_hint"] = "offline mode; skipped network verification"
        return card

    # Online but no stable identifier — try title search (Re8.0 second batch:
    # previously this short-circuited to ambiguous, leaving Seed Repair空转).
    # Re8.2 WP2: calls _fetch_by_title first (backward compat), then enhances
    # with _fetch_seed_candidates when the old path returns nothing. This
    # ordering preserves existing test mocking — tests that mock _fetch_by_title
    # continue to work without also mocking the 4 new adapters.
    if identifier is None:
        title = (flat.get("title") or "").strip()
        if input_form == "title" and title:
            fetched = await _fetch_by_title(
                title,
                list(flat.get("authors") or []),
                year=flat.get("year"),
            )
            # Re8.2 WP2: when _fetch_by_title returns nothing, try the
            # enhanced multi-strategy + structured scoring path.
            if fetched is None:
                fetched = await _fetch_seed_candidates(
                    title,
                    list(flat.get("authors") or []),
                    year=flat.get("year"),
                )
            if fetched is not None:
                status, hint = _status_from_fetched(flat, fetched)
                card = make_seed_card(
                    seed_id=seed_id,
                    input_form=input_form,
                    resolved_title=fetched.get("title") or flat.get("title"),
                    authors=fetched.get("authors") or list(flat.get("authors") or []),
                    year=fetched.get("year") or flat.get("year"),
                    doi=fetched.get("doi") or flat.get("doi"),
                    canonical_url=fetched.get("canonical_url") or flat.get("url"),
                    existence_status=status,
                    fulltext_status="metadata_only",
                    role=flat.get("role", "unknown"),
                    raw_input=payload,
                )
                if hint:
                    card["repair_hint"] = hint
                # Re8.1: propagate legacy fields
                for k in ("confidence", "ranking_reasons", "sources",
                          "conflict", "conflict_type", "all_candidates"):
                    if k in fetched:
                        card[k] = fetched[k]
                # Re8.2 WP2: propagate structured score fields
                for k in ("title_score", "author_score", "year_score",
                          "abstract_score", "identifier_score", "total_score",
                          "confidence_plan_b", "_disambiguation", "_llm_override"):
                    if k in fetched:
                        card[k] = fetched[k]
                return card
        # Fall through: no title or title search found no match
        card = make_seed_card(
            seed_id=seed_id,
            input_form=input_form,
            resolved_title=flat.get("title"),
            authors=list(flat.get("authors") or []),
            year=flat.get("year"),
            doi=flat.get("doi"),
            canonical_url=flat.get("url"),
            existence_status="ambiguous",
            fulltext_status="metadata_only",
            role=flat.get("role", "unknown"),
            raw_input=payload,
        )
        card["repair_hint"] = (
            "no stable identifier; title search found no authoritative match"
        )
        return card

    # Online: fetch metadata
    fetched: dict[str, Any] | None = None
    if input_form == "doi":
        fetched = await _fetch_crossref(identifier)
        # Re8.2 WP4 fallback: authoritative Crossref fetch can fail or return
        # an empty metadata shell due to transient network/SSL errors. If the
        # fetched record lacks a usable title, try the Seed Repair 2.0
        # multi-source search path as a safety net.
        if (fetched is None or not (fetched.get("title") or "").strip()) and (flat.get("title") or "").strip():
            fetched = await _fetch_seed_candidates(
                (flat.get("title") or "").strip(),
                list(flat.get("authors") or []),
                year=flat.get("year"),
            )
    elif input_form == "arxiv":
        fetched = await _fetch_arxiv(identifier)
        if (fetched is None or not (fetched.get("title") or "").strip()) and (flat.get("title") or "").strip():
            fetched = await _fetch_seed_candidates(
                (flat.get("title") or "").strip(),
                list(flat.get("authors") or []),
                year=flat.get("year"),
            )
    elif input_form == "url":
        # Try arxiv pattern first (P1-1: use unanchored _ARXIV_URL_RE)
        if "arxiv.org" in (identifier or "").lower():
            m = _ARXIV_URL_RE.search(identifier)
            if m:
                fetched = await _fetch_arxiv(m.group(1))
            if (fetched is None or not (fetched.get("title") or "").strip()) and (flat.get("title") or "").strip():
                fetched = await _fetch_seed_candidates(
                    (flat.get("title") or "").strip(),
                    list(flat.get("authors") or []),
                    year=flat.get("year"),
                )
        # Else fall through — URL-only is metadata_only ambiguous unless
        # caller also supplied a DOI/arxiv that we already tried above.

    status, hint = _status_from_fetched(flat, fetched)

    # Merge fetched metadata into card (fetched wins on conflicts)
    card = make_seed_card(
        seed_id=seed_id,
        input_form=input_form,
        resolved_title=(fetched or {}).get("title") or flat.get("title"),
        authors=(fetched or {}).get("authors") or list(flat.get("authors") or []),
        year=(fetched or {}).get("year") or flat.get("year"),
        doi=(fetched or {}).get("doi") or flat.get("doi"),
        canonical_url=(fetched or {}).get("canonical_url") or flat.get("url"),
        existence_status=status,
        fulltext_status="metadata_only",
        role=flat.get("role", "unknown"),
        raw_input=payload,
    )
    if hint:
        card["repair_hint"] = hint
    return card


# ── LangGraph node ──────────────────────────────────────────────────────────

def seed_resolver_node(state: ResearchState) -> dict[str, Any]:
    """Resolve candidate seeds into SeedPaperCards; promote verified to evidence.

    Behaviour:
      - No-op when entry_mode == "topic_only" (backward compat for Re7 callers)
      - No-op when candidate_seeds is empty (no user papers to audit)
      - In offline mode, all cards become ambiguous (no network)
      - Verified cards (with stable identifier) are appended to verified_papers
        and seed_papers so downstream Re6/Re7 nodes treat them as evidence
      - Ambiguous / not_found cards stay in seed_cards only
      - Each resolution decision is appended to reasoning_ledger
    """
    t0 = time.time()
    errors: list[dict[str, Any]] = []

    entry_mode = state.get("entry_mode") or "topic_only"
    candidate_seeds = state.get("candidate_seeds") or []
    network_policy = state.get("network_policy") or "online"

    # No-op conditions
    if entry_mode == "topic_only" or not candidate_seeds:
        trace = _emit(
            "seed_resolver", t0,
            {"entry_mode": entry_mode, "n_candidates": len(candidate_seeds)},
            {"n_resolved": 0, "n_verified": 0, "n_ambiguous": 0, "n_not_found": 0, "skipped": True},
            [], "local", [],
            state_keys=["seed_cards", "verified_papers", "seed_papers",
                        "reasoning_ledger", "trace_events", "errors"],
        )
        return {"trace_events": [trace]}

    # Resolve all seeds concurrently
    offline = network_policy == "offline"

    async def _resolve_all() -> list[dict[str, Any]]:
        tasks = [
            _resolve_one_seed(seed.get("seed_id") or f"seed-{i}", seed, offline=offline)
            for i, seed in enumerate(candidate_seeds)
        ]
        return await asyncio.gather(*tasks)

    try:
        cards = asyncio.run(_resolve_all())
    except RuntimeError:
        # No event loop in thread — fall back to sequential
        cards = []
        loop = asyncio.new_event_loop()
        try:
            for i, seed in enumerate(candidate_seeds):
                sid = seed.get("seed_id") or f"seed-{i}"
                cards.append(loop.run_until_complete(
                    _resolve_one_seed(sid, seed, offline=offline)
                ))
        finally:
            loop.close()

    # Validate cards + split by status
    verified_cards: list[dict[str, Any]] = []
    n_verified = n_ambiguous = n_not_found = 0
    ledger_entries: list[dict[str, Any]] = []

    for card in cards:
        errs = validate_seed_card(card)
        if errs:
            errors.append({
                "node": "seed_resolver",
                "seed_id": card.get("seed_id"),
                "error": "schema_invalid",
                "detail": errs,
            })
            # Treat schema-invalid cards as not_found rather than dropping
            card["existence_status"] = "not_found"
            card["repair_hint"] = f"schema invalid: {errs}"

        status = card.get("existence_status", "ambiguous")
        if status == "verified":
            n_verified += 1
            if is_seed_evidence_eligible(card):
                verified_cards.append(card)
        elif status == "ambiguous":
            n_ambiguous += 1
        else:
            n_not_found += 1

        # Audit ledger entry for each seed
        ledger_entries.append(make_ledger_entry(
            decision_id=f"seed-audit-{card.get('seed_id')}",
            stage="seed_audit",
            decision=f"seed {card.get('seed_id')} → {status}",
            evidence_ids=[card["seed_id"]] if status == "verified" else [],
            alternatives_considered=[],
            rejection_reasons=[card.get("repair_hint", "")] if card.get("repair_hint") else [],
            next_action="promote_to_evidence" if status == "verified" else "await_repair_or_user",
            confidence=0.9 if status == "verified" else (0.4 if status == "ambiguous" else 0.1),
            status="verified" if status == "verified" else "unresolved",
        ))

    # Promote verified cards to verified_papers + seed_papers
    new_verified_papers: list[dict[str, Any]] = []
    new_seed_papers: list[dict[str, Any]] = []
    for card in verified_cards:
        new_verified_papers.append({
            "title": card.get("resolved_title") or "",
            "abstract": card.get("raw_input", {}).get("abstract", ""),
            "url": card.get("canonical_url") or "",
            "doi": card.get("doi"),
            "arxiv_id": card.get("raw_input", {}).get("arxiv_id"),
            "source": "user_seed_verified",
            "verdict": "accept",
            "relation_to_topic": card.get("role", "baseline"),
            "relevance_score": 1.0,
            "seed_id": card.get("seed_id"),
        })
        new_seed_papers.append({
            "title": card.get("resolved_title") or "",
            "url": card.get("canonical_url") or "",
            "doi": card.get("doi"),
            "relevance_score": 1.0,
            "seed_id": card.get("seed_id"),
        })

    trace = _emit(
        "seed_resolver", t0,
        {"entry_mode": entry_mode, "n_candidates": len(candidate_seeds),
         "network_policy": network_policy},
        {"n_resolved": len(cards), "n_verified": n_verified,
         "n_ambiguous": n_ambiguous, "n_not_found": n_not_found,
         "n_promoted_to_evidence": len(verified_cards)},
        [{"tool": "crossref+arxiv", "mode": "offline" if offline else "online"}],
        "local", errors,
        state_keys=["seed_cards", "verified_papers", "seed_papers",
                    "reasoning_ledger", "trace_events", "errors"],
    )

    return {
        "seed_cards": cards,
        "verified_papers": new_verified_papers,
        "seed_papers": new_seed_papers,
        "reasoning_ledger": ledger_entries,
        "trace_events": [trace],
        "errors": errors,
    }
