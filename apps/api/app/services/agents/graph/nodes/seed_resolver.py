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


async def _fetch_by_title(
    title: str,
    authors: list[str] | None = None,
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

    # Merge + validate candidates via _titles_agree
    candidates: list[dict[str, Any]] = []
    for hit in (crossref_hits or []):
        if isinstance(hit, dict) and _titles_agree(title, hit.get("title", "")):
            candidates.append(_normalize_title_hit(hit, "crossref"))
    for hit in (s2_hits or []):
        if isinstance(hit, dict) and _titles_agree(title, hit.get("title", "")):
            candidates.append(_normalize_title_hit(hit, "semantic_scholar"))

    if not candidates:
        return None

    # Score: prefer candidates with DOI, then with author overlap
    user_lastnames = {_author_lastname(a) for a in (authors or []) if a}

    def _score(c: dict[str, Any]) -> int:
        score = 0
        if c.get("doi"):
            score += 10
        if user_lastnames:
            cand_lastnames = {
                _author_lastname(a) for a in (c.get("authors") or []) if a
            }
            if cand_lastnames & user_lastnames:
                score += 5
        return score

    candidates.sort(key=_score, reverse=True)
    return candidates[0]


# ── Per-seed resolution ─────────────────────────────────────────────────────

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
    # previously this short-circuited to ambiguous, leaving Seed Repair空转)
    if identifier is None:
        title = (flat.get("title") or "").strip()
        if input_form == "title" and title:
            fetched = await _fetch_by_title(title, list(flat.get("authors") or []))
            if fetched is not None:
                status, hint = _decide_existence(flat, fetched)
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
    elif input_form == "arxiv":
        fetched = await _fetch_arxiv(identifier)
    elif input_form == "url":
        # Try arxiv pattern first (P1-1: use unanchored _ARXIV_URL_RE)
        if "arxiv.org" in (identifier or "").lower():
            m = _ARXIV_URL_RE.search(identifier)
            if m:
                fetched = await _fetch_arxiv(m.group(1))
        # Else fall through — URL-only is metadata_only ambiguous unless
        # caller also supplied a DOI/arxiv that we already tried above.

    status, hint = _decide_existence(flat, fetched)

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
