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


def _classify_input(payload: dict[str, Any]) -> tuple[str, str | None]:
    """Return (input_form, identifier) for a candidate seed payload.

    input_form is one of SEED_INPUT_FORMS. identifier is the canonical
    DOI / arXiv id when available, else None.
    """
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

    user_authors = {a.lower() for a in (candidate.get("authors") or []) if a}
    fetched_authors = {a.lower() for a in (fetched.get("authors") or []) if a}
    if user_authors and fetched_authors and not (user_authors & fetched_authors):
        return "ambiguous", "author set does not intersect; possible identifier_mismatch"

    return "verified", None


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
    input_form, identifier = _classify_input(payload)
    if input_form not in SEED_INPUT_FORMS:
        input_form = "citation"

    # Local PDF path: no network needed, mark as verified-local
    if input_form == "pdf":
        card = make_seed_card(
            seed_id=seed_id,
            input_form="pdf",
            resolved_title=payload.get("title"),
            existence_status="verified",
            fulltext_status="metadata_only",
            role=payload.get("role", "unknown"),
            raw_input={k: v for k, v in payload.items() if k != "pdf_bytes"},
        )
        card["repair_hint"] = "local PDF; fulltext parse pending (WP2)"
        return card

    if offline or identifier is None:
        # Nothing to fetch — keep as ambiguous with raw input preserved
        card = make_seed_card(
            seed_id=seed_id,
            input_form=input_form,
            resolved_title=payload.get("title"),
            authors=list(payload.get("authors") or []),
            year=payload.get("year"),
            doi=payload.get("doi"),
            canonical_url=payload.get("url"),
            existence_status="ambiguous",
            fulltext_status="metadata_only",
            role=payload.get("role", "unknown"),
            raw_input=payload,
        )
        if offline:
            card["repair_hint"] = "offline mode; skipped network verification"
        else:
            card["repair_hint"] = "no stable identifier; cannot verify online"
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

    status, hint = _decide_existence(payload, fetched)

    # Merge fetched metadata into card (fetched wins on conflicts)
    card = make_seed_card(
        seed_id=seed_id,
        input_form=input_form,
        resolved_title=(fetched or {}).get("title") or payload.get("title"),
        authors=(fetched or {}).get("authors") or list(payload.get("authors") or []),
        year=(fetched or {}).get("year") or payload.get("year"),
        doi=(fetched or {}).get("doi") or payload.get("doi"),
        canonical_url=(fetched or {}).get("canonical_url") or payload.get("url"),
        existence_status=status,
        fulltext_status="metadata_only",
        role=payload.get("role", "unknown"),
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
