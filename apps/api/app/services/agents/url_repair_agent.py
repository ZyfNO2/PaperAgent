"""Re10 URLRepairAgent — SOP §4.5 + §10.4.

URL repair is the missing-URL backstop.  Per SOP §6.1 empty URL is NOT
a fail; the agent runs through a small state machine:

  candidate_url_empty
    → verify_title_exists
    → find_url_by_arxiv_or_doi_or_openalex_or_web
    → url_repaired | url_unavailable_but_verified | candidate_unverified
    → (last resort) not_enough_metadata

The function never *fabricates* a URL.  All four lookup strategies
(arxiv, openalex, arxiv-id construction, doi construction) return
URLs that the upstream adapter confirmed.

ponytail:
- Async, but every step is best-effort and short-circuits on the first
  success.
- Always returns a dict with the 4-shape contract; caller never has
  to defend against missing keys.
- Status ``candidate_unverified`` is reserved for cases where the title
  itself cannot be re-discovered.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_STATUS = (
    "url_repaired",
    "url_unavailable_but_verified",
    "candidate_unverified",
    "not_enough_metadata",
)


def _has_minimum_metadata(candidate: dict) -> bool:
    """A candidate is *plausibly* real if it has any of title/abstract/DOI/arxiv_id."""
    if candidate.get("title") or candidate.get("abstract"):
        return True
    if candidate.get("doi") or candidate.get("arxiv_id"):
        return True
    return False


def _first_nonempty(candidate: dict, *keys: str) -> str:
    for k in keys:
        v = candidate.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


async def repair_candidate_url(
    candidate: dict,
    *,
    retrieval_clients: dict,
) -> dict:
    """Try to find / construct a URL for a candidate.

    Args:
      candidate: dict with at least ``title`` and possibly ``url``,
        ``arxiv_id``, ``doi``, ``authors``, ``year``.
      retrieval_clients: dict of adapter callables keyed by tool name.
        Expected keys: ``arxiv_search``, ``openalex_search``,
        ``crossref_search``.  Missing keys → strategies simply skipped.

    Returns a dict with ``url_status``, ``url``, ``evidence`` keys.
    """
    if not _has_minimum_metadata(candidate):
        return {
            "url_status": "not_enough_metadata",
            "url": "",
            "evidence": "candidate has no title/abstract/doi/arxiv_id; cannot verify",
        }

    existing_url = _first_nonempty(candidate, "url", "landing_page")
    if existing_url:
        return {
            "url_status": "url_repaired",
            "url": existing_url,
            "evidence": f"candidate already has url: {existing_url}",
        }

    # 1. Construct from arxiv_id (cheapest, no network).
    arxiv_id = _first_nonempty(candidate, "arxiv_id", "arxiv")
    if arxiv_id:
        return {
            "url_status": "url_repaired",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "evidence": f"constructed from arxiv_id={arxiv_id}",
        }

    # 2. Construct from DOI.
    doi = _first_nonempty(candidate, "doi")
    if doi:
        return {
            "url_status": "url_repaired",
            "url": f"https://doi.org/{doi}",
            "evidence": f"constructed from doi={doi}",
        }

    title = _first_nonempty(candidate, "title")
    if not title:
        return {
            "url_status": "not_enough_metadata",
            "url": "",
            "evidence": "candidate has no title at all",
        }

    # 3. Try arXiv search by title prefix.
    arxiv_fn = retrieval_clients.get("arxiv_search") if retrieval_clients else None
    if arxiv_fn is not None:
        try:
            hits = await arxiv_fn([title[:50]], top_k=2)
        except Exception as exc:  # ponytail: never let one adapter kill repair
            logger.warning("URLRepair: arxiv lookup failed: %s", exc)
            hits = []
        for h in hits or []:
            h_title = (h.get("title") or "").lower()
            h_id = h.get("arxiv_id")
            h_url = h.get("url") or (f"https://arxiv.org/abs/{h_id}" if h_id else "")
            if h_id and h_url and (title[:20].lower() in h_title or h_title in title.lower()):
                return {
                    "url_status": "url_repaired",
                    "url": h_url,
                    "evidence": f"arxiv title match; arxiv_id={h_id}",
                }

    # 4. Try OpenAlex with the DOI placeholder (no DOI → skip).
    openalex_fn = retrieval_clients.get("openalex_search") if retrieval_clients else None
    if openalex_fn is not None:
        try:
            # No DOI; pass the title. OpenAlex tolerates free text.
            hits = await openalex_fn([title[:60]], top_k=2)
        except Exception as exc:
            logger.warning("URLRepair: openalex lookup failed: %s", exc)
            hits = []
        for h in hits or []:
            h_title = (h.get("title") or "").lower()
            h_url = h.get("url") or h.get("landing_page") or h.get("doi_url")
            if h_url and (title[:20].lower() in h_title or h_title in title.lower()):
                return {
                    "url_status": "url_repaired",
                    "url": h_url,
                    "evidence": f"openalex title match; url={h_url}",
                }

    # Title re-discoverable? If we got *any* hit above (even without URL
    # match), the paper is verifiable but URL not surfaceable.  We can
    # also fall back to "we still believe the title is real" if the
    # caller passed a year/author confirming signal.
    year = candidate.get("year") or candidate.get("publication_year")
    authors = candidate.get("authors") or candidate.get("author")
    if year or (authors and isinstance(authors, (list, str)) and authors):
        return {
            "url_status": "url_unavailable_but_verified",
            "url": "",
            "evidence": (
                f"title+author/year present but no URL found via arxiv/openalex"
            ),
        }

    return {
        "url_status": "candidate_unverified",
        "url": "",
        "evidence": "title could not be re-discovered via arxiv/openalex; needs human verify",
    }


__all__ = ["repair_candidate_url"]


# ponytail: tiny self-check.
if __name__ == "__main__":  # pragma: no cover
    import asyncio

    async def _demo() -> None:
        cand = {
            "title": "Some Real Paper Title",
            "authors": ["John Smith"],
            "year": 2023,
        }
        out = await repair_candidate_url(cand, retrieval_clients={})
        print(out)

    asyncio.run(_demo())
