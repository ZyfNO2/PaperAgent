"""Re03 SOP §6.1: citation_expand ledger honesty tests (SOP §1.4).

Verifies that citation_expand:
  - NEVER writes a pre-record `status=ok result_count=N(seeds)` before fetch
  - Writes one row per seed with explicit status: seed_selected /
    seed_rejected / refs_ok / refs_empty / refs_error
  - Returns stats with seeds_total/eligible/rejected/refs_added
"""

import pytest

from app.services.agents.candidate_pool import CandidatePool
from app.services.agents.citation_expand import citation_expand
from app.services.agents.source_ledger import SourceLedger


def _fake_fetch_factory(per_seed_refs: dict | None = None):
    """Returns a fetch that returns per_seed_refs for `select=referenced_works`
    and per-seed metadata for batched `?select=id,title,...`.

    If `per_seed_refs` is None, returns 3 refs (W1, W2, W3) for any
    referenced_works URL.
    """
    if per_seed_refs is None:
        per_seed_refs = {"*": ["W1", "W2", "W3"]}
    async def _f(url, headers, timeout):
        if "select=referenced_works" in url:
            for seed_key, refs in per_seed_refs.items():
                if seed_key == "*" or seed_key in url:
                    return {"referenced_works": [f"https://openalex.org/{r}" for r in refs]}
            return {"referenced_works": []}
        # Batch metadata — return rows for each ref id in the URL
        rows = []
        for ref_id, title in (
            ("W1", "Ref 1"), ("W2", "Ref 2"), ("W3", "Ref 3"),
            ("W4", "Ref 4"), ("W5", "Ref 5"),
        ):
            if ref_id in url:
                rows.append({"id": f"https://openalex.org/{ref_id}", "title": title, "publication_year": 2020})
        return {"results": rows}
    return _f


@pytest.mark.asyncio
async def test_no_pre_record_in_ledger_before_fetch():
    """Citation_expand must NOT write any ledger row before the first seed's
    fetch happens. The old Re02 code wrote a fake `references of 5 seed
    paper(s)` row at the top of the function."""
    raw = {
        "arxiv": [{"title": "U-Net steel crack segmentation",
                   "arxiv_id": "2103.00020",
                   "candidate_id": "c-1"}],
    }
    pool = CandidatePool()
    ledger = SourceLedger()
    fetch = _fake_fetch_factory()
    await citation_expand(
        raw=raw, pool=pool, fetch=fetch,
        parsed_topic={
            "method_terms": ["U-Net"],
            "task_terms": ["crack segmentation"],
            "object_terms": ["steel plate"],
            "query_atoms_en": ["U-Net steel crack"],
            "domain_route": "vision_2d",
        },
        ledger=ledger,
    )
    rows = ledger.as_list()
    # All rows must have explicit per-seed status, NOT a fake "ok result_count=1"
    for r in rows:
        assert r["status"] in {"seed_selected", "seed_rejected",
                                "refs_ok", "refs_empty", "refs_error"}, \
            f"unexpected ledger status: {r['status']}"
        # No row should claim `refs_ok` with query='references of N seed paper(s)'
        # (the old pre-record)
        assert "references of" not in r["query"].lower() or "seed_" in r["status"]


@pytest.mark.asyncio
async def test_seed_selected_then_refs_ok_ledger_sequence():
    raw = {
        "arxiv": [{"title": "U-Net steel crack segmentation",
                   "arxiv_id": "2103.00020",
                   "candidate_id": "c-1"}],
    }
    pool = CandidatePool()
    ledger = SourceLedger()
    fetch = _fake_fetch_factory()
    await citation_expand(
        raw=raw, pool=pool, fetch=fetch,
        parsed_topic={
            "method_terms": ["U-Net"],
            "task_terms": ["crack segmentation"],
            "object_terms": ["steel"],
            "query_atoms_en": ["U-Net steel crack"],
        },
        ledger=ledger,
    )
    rows = ledger.as_list()
    statuses = [r["status"] for r in rows]
    assert "seed_selected" in statuses
    assert "refs_ok" in statuses


@pytest.mark.asyncio
async def test_seed_rejected_logged_with_reason_in_query():
    raw = {
        "arxiv": [{"title": "Cosmic ray at CERN",
                   "arxiv_id": "2103.00020",
                   "candidate_id": "c-cosmic"}],
    }
    pool = CandidatePool()
    ledger = SourceLedger()
    fetch = _fake_fetch_factory({})  # no refs to fetch
    await citation_expand(
        raw=raw, pool=pool, fetch=fetch,
        parsed_topic={
            "method_terms": ["U-Net"],
            "task_terms": ["crack segmentation"],
            "object_terms": ["steel"],
            "query_atoms_en": ["U-Net steel crack"],
        },
        ledger=ledger,
    )
    rows = ledger.as_list()
    assert any(r["status"] == "seed_rejected" for r in rows)


@pytest.mark.asyncio
async def test_stats_dict_has_required_keys():
    raw = {
        "arxiv": [{"title": "U-Net steel crack",
                   "arxiv_id": "2103.00020",
                   "candidate_id": "c-1"}],
    }
    pool = CandidatePool()
    fetch = _fake_fetch_factory()
    stats = await citation_expand(
        raw=raw, pool=pool, fetch=fetch,
        parsed_topic={
            "method_terms": ["U-Net"],
            "task_terms": ["crack segmentation"],
            "object_terms": ["steel"],
            "query_atoms_en": ["U-Net steel crack"],
        },
    )
    for k in ("seeds_total", "seeds_eligible", "seeds_rejected",
              "refs_added", "round_status"):
        assert k in stats, f"missing key in stats: {k}"


@pytest.mark.asyncio
async def test_no_seeds_returns_no_seeds_status():
    raw = {"arxiv": []}  # no seeds (no arxiv_id, doi, etc.)
    pool = CandidatePool()
    stats = await citation_expand(raw=raw, pool=pool, fetch=_fake_fetch_factory({}))
    assert stats["round_status"] == "no_seeds"
    assert stats["seeds_total"] == 0
