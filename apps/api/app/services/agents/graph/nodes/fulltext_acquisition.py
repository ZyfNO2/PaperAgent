"""Re8.0 P1-1: Fulltext Acquisition — download PDF fulltext for verified seeds.

Bridges the gap between ``seed_resolver`` (which only fetches metadata) and
``paper_understanding`` (which only reads local PDFs). For seed cards that
were verified online via DOI or arXiv but have no local PDF, this node
downloads the actual PDF bytes so downstream paper_understanding can parse
method/dataset/environment fields on a subsequent pass (or re-loop).

Acquisition paths (per card):
  - DOI  → Unpaywall ``best_oa_location.url_for_pdf`` → download
  - arXiv→ ``https://arxiv.org/pdf/{arxiv_id}`` → download

State transitions on the SeedPaperCard:
  - metadata_only → fulltext_available   (download succeeded)
  - metadata_only → metadata_only + gap  (paywall / 403 / timeout / no OA)

The node is a no-op when:
  - ``entry_mode != "seeded_research"`` (topic_only callers see no change)
  - no seed card has ``existence_status="verified"`` AND
    ``fulltext_status="metadata_only"`` (idempotent on re-runs)
  - ``network_policy == "offline"`` (graceful skip, no gaps opened —
    Offline Replay must remain hermetic)

This node does NOT parse PDF content — that is paper_understanding's job.
It only downloads bytes and stores them on the card for a downstream
re-parse pass.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.re80_schema import make_evidence_gap
from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.network_guard import NetworkPolicyGuard
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


# ── Constants ───────────────────────────────────────────────────────────────

_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB hard limit
_DOWNLOAD_TIMEOUT = 30.0           # seconds
_UNPAYWALL_TIMEOUT = 10.0          # seconds for the metadata API call
_UNPAYWALL_EMAIL = "test@example.com"
_USER_AGENT = "PaperAgent/1.0 (fulltext-acquisition)"

# Unanchored arXiv ID extractor (mirrors seed_resolver._ARXIV_URL_RE so we
# can pull the id out of canonical_url / raw_input.url without importing a
# private helper from another node module).
_ARXIV_URL_RE = re.compile(
    r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-.]+/\d{7})", re.IGNORECASE,
)


# ── Identifier extraction ───────────────────────────────────────────────────

def _extract_arxiv_id(card: dict[str, Any]) -> str | None:
    """Extract an arXiv ID from a seed card if available.

    Checks (in order):
      1. ``raw_input.arxiv_id`` — user-supplied identifier
      2. ``card.canonical_url`` — set by seed_resolver for arXiv seeds
      3. ``raw_input.url`` — original URL if the seed was URL-typed

    Returns the stripped arXiv ID string, or None.
    """
    raw = card.get("raw_input") or {}
    if not isinstance(raw, dict):
        raw = {}

    arxiv_id = (raw.get("arxiv_id") or "").strip()
    if arxiv_id:
        return arxiv_id

    for url in (card.get("canonical_url"), raw.get("url")):
        if url and isinstance(url, str) and "arxiv.org" in url.lower():
            m = _ARXIV_URL_RE.search(url)
            if m:
                return m.group(1)
    return None


# ── PDF URL resolution ─────────────────────────────────────────────────────

async def _get_unpaywall_pdf_url(doi: str) -> str | None:
    """Query Unpaywall for the best OA PDF URL for a DOI.

    Returns the ``url_for_pdf`` from ``best_oa_location``, falling back to
    the first ``oa_locations`` entry that has one. Returns None if the API
    call fails, the DOI is unknown, or no OA location carries a PDF URL.
    """
    NetworkPolicyGuard.assert_online("fulltext_acquisition")
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=_UNPAYWALL_TIMEOUT,
            follow_redirects=True,
            proxy=None,
            verify=False,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(
                f"https://api.unpaywall.org/v2/{doi}?email={_UNPAYWALL_EMAIL}",
            )
            if resp.status_code != 200:
                return None
            data = resp.json() or {}

            best = data.get("best_oa_location") or {}
            if isinstance(best, dict):
                url = (best.get("url_for_pdf") or "").strip()
                if url:
                    return url

            for loc in data.get("oa_locations") or []:
                if isinstance(loc, dict):
                    url = (loc.get("url_for_pdf") or "").strip()
                    if url:
                        return url
            return None
    except Exception as exc:
        logger.debug("unpaywall lookup failed for %s: %s", doi, exc)
        return None


# ── PDF download (streaming, size-capped) ───────────────────────────────────

async def _download_pdf(url: str) -> bytes:
    """Download PDF bytes from ``url`` with a hard size cap.

    Uses streaming so we can abort mid-download if the response exceeds
    ``_MAX_PDF_BYTES``. Raises on any HTTP error, timeout, or size
    violation — the caller is expected to catch and open an evidence gap.
    """
    NetworkPolicyGuard.assert_online("fulltext_acquisition")
    import httpx

    async with httpx.AsyncClient(
        timeout=_DOWNLOAD_TIMEOUT,
        follow_redirects=True,
        proxy=None,
        verify=False,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()

            # Pre-check Content-Length if the server sent one.
            content_length = resp.headers.get("content-length")
            if content_length:
                try:
                    cl = int(content_length)
                    if cl > _MAX_PDF_BYTES:
                        raise ValueError(
                            f"PDF too large: {cl} bytes (limit {_MAX_PDF_BYTES})"
                        )
                except ValueError:
                    # Non-integer content-length — skip pre-check, rely on
                    # the streaming guard below.
                    pass

            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > _MAX_PDF_BYTES:
                    raise ValueError(
                        f"PDF exceeded {_MAX_PDF_BYTES} bytes during download"
                    )
                chunks.append(chunk)

            data = b"".join(chunks)
            if not data:
                raise ValueError("empty response body")
            return data


# ── Evidence gap construction ───────────────────────────────────────────────

def _make_fulltext_gap(card: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build an EvidenceGap for a failed fulltext download."""
    seed_id = card.get("seed_id", "unknown")
    title = card.get("resolved_title") or seed_id
    return make_evidence_gap(
        gap_id=f"gap-{seed_id}-fulltext",
        question=f"What is the fulltext content of paper '{title}'?",
        gap_type="fulltext",
        why_needed=(
            f"PDF fulltext could not be downloaded ({reason}); downstream "
            f"paper understanding needs fulltext to extract method, "
            f"dataset, and reproduction environment."
        ),
        related_claim_ids=[seed_id],
        success_condition="Fulltext PDF successfully downloaded and parsed",
        status="open",
    )


# ── Per-card acquisition ────────────────────────────────────────────────────

async def _acquire_fulltext_for_card(
    card: dict[str, Any],
) -> dict[str, Any] | None:
    """Try to download fulltext for a single card.

    Mutates ``card`` in place on success (sets ``fulltext_status`` and
    ``pdf_bytes``). Returns an EvidenceGap dict on failure, or None on
    success / no-op-skip (card has no DOI or arXiv identifier to try).
    """
    doi = (card.get("doi") or "").strip()
    arxiv_id = _extract_arxiv_id(card)

    if not doi and not arxiv_id:
        # Nothing to try — the card was verified but carries neither a DOI
        # nor an arXiv identifier we can download from. Skip silently.
        return None

    # Resolve a PDF URL. DOI → Unpaywall first; if that yields nothing,
    # fall back to arXiv if available.
    pdf_url: str | None = None
    if doi:
        try:
            pdf_url = await _get_unpaywall_pdf_url(doi)
        except Exception as exc:
            logger.debug(
                "unpaywall lookup error for %s: %s", doi, exc,
            )
            pdf_url = None

    if pdf_url is None and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    if pdf_url is None:
        # Had an identifier but no open-access PDF URL (paywall).
        return _make_fulltext_gap(card, "no open-access PDF URL available (paywall)")

    # Download
    try:
        pdf_bytes = await _download_pdf(pdf_url)
    except Exception as exc:
        logger.warning(
            "PDF download failed for seed %s from %s: %s",
            card.get("seed_id"), pdf_url, exc,
        )
        return _make_fulltext_gap(card, f"download failed: {exc}")

    card["fulltext_status"] = "fulltext_available"
    card["pdf_bytes"] = pdf_bytes
    return None


# ── LangGraph node ──────────────────────────────────────────────────────────

def fulltext_acquisition_node(state: ResearchState) -> dict[str, Any]:
    """Re8.0 P1-1: download PDF fulltext for verified seed cards.

    Iterates over ``state["seed_cards"]`` and, for each card with
    ``existence_status="verified"`` AND ``fulltext_status="metadata_only"``,
    attempts to download the PDF via Unpaywall (DOI) or arXiv direct URL.

    On success the card is mutated in place (``fulltext_status`` →
    ``fulltext_available``, ``pdf_bytes`` stored). On failure an
    ``EvidenceGap`` with ``gap_type="fulltext"`` is opened.

    No-op for ``topic_only`` entry mode, offline network policy, or when
    no card needs acquisition (idempotent on re-runs).
    """
    t0 = time.time()
    entry_mode = state.get("entry_mode") or "topic_only"
    seed_cards: list[dict[str, Any]] = list(state.get("seed_cards") or [])
    network_policy = state.get("network_policy") or "online"
    errors: list[dict[str, Any]] = []

    # No-op: topic_only or no seed_cards
    if entry_mode != "seeded_research" or not seed_cards:
        trace = _emit(
            "fulltext_acquisition", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards)},
            {"skipped": True,
             "reason": "topic_only or no seed_cards"},
            [], "local", [],
            state_keys=["seed_cards", "evidence_gaps", "trace_events", "errors"],
        )
        return {"trace_events": [trace]}

    # No-op: offline mode — graceful skip, no gaps opened (Offline Replay
    # must remain hermetic; seed_resolver already marked cards ambiguous).
    if NetworkPolicyGuard.is_offline() or network_policy == "offline":
        trace = _emit(
            "fulltext_acquisition", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards),
             "network_policy": network_policy},
            {"skipped": True, "reason": "offline mode"},
            [], "local", [],
            state_keys=["seed_cards", "evidence_gaps", "trace_events", "errors"],
        )
        return {"trace_events": [trace]}

    # Filter to cards that need acquisition (idempotent: skip cards that
    # already have fulltext_available / downloaded / parse_failed).
    target_cards = [
        c for c in seed_cards
        if c.get("existence_status") == "verified"
        and c.get("fulltext_status") == "metadata_only"
    ]

    if not target_cards:
        trace = _emit(
            "fulltext_acquisition", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards),
             "n_target": 0},
            {"skipped": True,
             "reason": "no verified metadata_only cards"},
            [], "local", [],
            state_keys=["seed_cards", "evidence_gaps", "trace_events", "errors"],
        )
        return {"trace_events": [trace]}

    # Download concurrently. gather(return_exceptions=True) ensures one
    # card failure doesn't crash the batch — though _acquire_fulltext_for_card
    # already catches internally, this is a defensive second net.
    async def _download_all() -> list[Any]:
        tasks = [_acquire_fulltext_for_card(c) for c in target_cards]
        return await asyncio.gather(*tasks, return_exceptions=True)

    try:
        gap_results = asyncio.run(_download_all())
    except RuntimeError:
        # No running event loop in this thread — fall back to sequential.
        gap_results = []
        loop = asyncio.new_event_loop()
        try:
            for c in target_cards:
                try:
                    gap_results.append(
                        loop.run_until_complete(_acquire_fulltext_for_card(c))
                    )
                except Exception as exc:
                    gap_results.append(exc)
        finally:
            loop.close()

    # Collect gaps + errors from results
    new_gaps: list[dict[str, Any]] = []
    n_downloaded = 0
    n_failed = 0
    n_skipped = 0

    for card, result in zip(target_cards, gap_results):
        if isinstance(result, Exception):
            # Defensive: _acquire_fulltext_for_card catches internally, so
            # this branch should rarely fire. Treat as a download failure.
            sid = card.get("seed_id", "unknown")
            errors.append({
                "seed_id": sid,
                "error": "acquisition_exception",
                "detail": str(result),
            })
            new_gaps.append(
                _make_fulltext_gap(card, f"unexpected error: {result}")
            )
            n_failed += 1
        elif result is None:
            # Either success (card mutated) or no-identifier skip.
            if card.get("fulltext_status") == "fulltext_available":
                n_downloaded += 1
            else:
                n_skipped += 1
        else:
            # result is an EvidenceGap dict → download failed (paywall/403/...)
            new_gaps.append(result)
            n_failed += 1

    trace = _emit(
        "fulltext_acquisition", t0,
        {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards),
         "n_target": len(target_cards), "network_policy": network_policy},
        {"n_downloaded": n_downloaded, "n_failed": n_failed,
         "n_skipped": n_skipped, "n_gaps_opened": len(new_gaps)},
        [{"tool": "unpaywall", "endpoint": "api.unpaywall.org"},
         {"tool": "arxiv_pdf", "endpoint": "arxiv.org/pdf"},
         {"tool": "httpx.stream", "timeout": _DOWNLOAD_TIMEOUT}],
        "httpx", errors,
        state_keys=["seed_cards", "evidence_gaps", "trace_events", "errors"],
    )

    result_patch: dict[str, Any] = {
        "seed_cards": seed_cards,  # cards mutated in place
        "trace_events": [trace],
    }
    if new_gaps:
        result_patch["evidence_gaps"] = (
            list(state.get("evidence_gaps") or []) + new_gaps
        )
    if errors:
        result_patch["errors"] = errors
    return result_patch
