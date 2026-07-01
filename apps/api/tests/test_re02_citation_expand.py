"""Tests for Re02 citation_expand Round 2.5 (paper refs -> parallel baselines).

Strategy: we never hit the real OpenAlex API in unit tests. The `_fetch`
parameter is injected as a fake function that returns canned
referenced_works and metadata dicts, exercising the add-to-pool logic.

The e2e test (optional, marked opt-in) does hit real OpenAlex but is
gated by an env var to avoid burning LLM quota in CI.
"""

from __future__ import annotations

import os
import pytest

from app.services.agents.candidate_pool import CandidatePool
from app.services.agents.citation_expand import (
    _seed_candidates,
    _to_oa_work_id,
    citation_expand,
    _fetch_work_refs,
    _fetch_refs_metadata,
)
from app.services.agents.source_ledger import SourceLedger


async def _fake_fetch_empty(url, headers, timeout):
    return {}


async def _fake_fetch_refs_factory(ref_ids):
    """Return a fetch that mirrors OpenAlex behavior:
    - URL with `?select=referenced_works` -> returns the ref_ids list
    - URL with `?select=id,title,...` (batch) -> returns metadata for those ids

    `ref_ids` is a list of strings like ["W100", "W200"] (with W prefix).
    """
    async def _f(url, headers, timeout):
        if "select=referenced_works" in url:
            return {"referenced_works": [f"https://openalex.org/{r}" for r in ref_ids]}
        # Batch metadata — only return rows for ids that appear in the URL
        in_url = [r for r in ref_ids if r in url]
        rows = [
            {
                "id": f"https://openalex.org/{r}",
                "title": f"Ref Paper {r}",
                "publication_year": 2020,
                "doi": f"10.1234/{r}",
                "type": "article",
            }
            for r in (in_url if in_url else ref_ids)
        ]
        return {"results": rows}
    return _f


def test_seed_candidates_prefers_arxiv_with_doi():
    raw = {
        "arxiv": [
            {"title": "Paper A", "arxiv_id": "2103.00020", "doi": "10.48550/arXiv.2103.00020"},
        ],
        "openalex": [
            {"title": "Paper B", "openalex_id": "W12345"},
        ],
        "crossref": [
            {"title": "Paper C", "doi": "10.1234/abc"},
        ],
        "github": [
            {"title": "Repo Z"},
        ],
    }
    seeds = _seed_candidates(raw)
    assert len(seeds) == 3
    assert seeds[0]["title"] == "Paper A"


def test_seed_candidates_dedups_by_title():
    raw = {
        "arxiv": [{"title": "Same", "arxiv_id": "2103.00020"}],
        "openalex": [{"title": "Same", "openalex_id": "W12345"}],
    }
    seeds = _seed_candidates(raw)
    assert len(seeds) == 1


def test_seed_candidates_caps_at_five():
    raw = {
        "arxiv": [
            {"title": f"P{i}", "arxiv_id": f"2103.0002{i}"}
            for i in range(10)
        ],
    }
    seeds = _seed_candidates(raw)
    assert len(seeds) == 5


def test_to_oa_work_id_openalex_id():
    assert _to_oa_work_id({"openalex_id": "W12345"}) == "W12345"
    assert _to_oa_work_id({"openalex_id": "https://openalex.org/W12345"}) == "W12345"


def test_to_oa_work_id_doi():
    assert _to_oa_work_id({"doi": "10.1234/abc"}) == "doi:10.1234/abc"
    assert _to_oa_work_id({"doi": "https://doi.org/10.1234/abc"}) == "doi:10.1234/abc"


def test_to_oa_work_id_arxiv_id():
    assert _to_oa_work_id({"arxiv_id": "2103.00020"}) == "doi:10.48550/arXiv.2103.00020"


def test_to_oa_work_id_none():
    assert _to_oa_work_id({"title": "no id"}) is None


@pytest.mark.asyncio
async def test_citation_expand_adds_pool_rows_from_seed_refs():
    raw = {
        "arxiv": [{"title": "Seed A", "arxiv_id": "2103.00020"}],
    }
    pool = CandidatePool()
    ledger = SourceLedger()
    fetch = await _fake_fetch_refs_factory(["W100", "W200"])
    added = await citation_expand(raw, pool, fetch=fetch, ledger=ledger)
    assert added == 2
    titles = {c.title for c in pool.all()}
    assert "Ref Paper W100" in titles
    assert "Ref Paper W200" in titles
    assert len(ledger.as_list()) >= 2


@pytest.mark.asyncio
async def test_citation_expand_handles_empty_referenced_works():
    raw = {
        "arxiv": [{"title": "Seed A", "arxiv_id": "2103.00020"}],
    }
    pool = CandidatePool()
    fetch = await _fake_fetch_refs_factory([])
    added = await citation_expand(raw, pool, fetch=fetch)
    assert added == 0
    assert pool.all() == []


@pytest.mark.asyncio
async def test_citation_expand_skips_when_no_seed():
    raw = {
        "arxiv": [{"title": "no id paper"}],
        "github": [{"title": "repo"}],
    }
    pool = CandidatePool()
    fetch = await _fake_fetch_refs_factory(["W1"])
    added = await citation_expand(raw, pool, fetch=fetch)
    assert added == 0
    assert pool.all() == []


@pytest.mark.asyncio
async def test_citation_expand_returns_zero_on_network_error():
    raw = {
        "arxiv": [{"title": "Seed A", "arxiv_id": "2103.00020"}],
    }
    pool = CandidatePool()
    added = await citation_expand(raw, pool, fetch=_fake_fetch_empty)
    assert added == 0


@pytest.mark.asyncio
async def test_citation_expand_caps_per_seed_at_eight():
    raw = {
        "arxiv": [{"title": "Seed A", "arxiv_id": "2103.00020"}],
    }
    pool = CandidatePool()
    fetch = await _fake_fetch_refs_factory([f"W{i}" for i in range(20)])
    added = await citation_expand(raw, pool, fetch=fetch)
    assert added == 8


@pytest.mark.asyncio
async def test_fetch_work_refs_returns_W_ids():
    async def _f(url, headers, timeout):
        return {"referenced_works": [
            "https://openalex.org/W12345",
            "W67890",
            "not-a-valid-id",
        ]}
    out = await _fetch_work_refs(_f, "W1")
    assert out == ["W12345", "W67890"]


@pytest.mark.asyncio
async def test_fetch_refs_metadata_normalizes_doi():
    async def _f(url, headers, timeout):
        return {"results": [{
            "id": "https://openalex.org/W999",
            "title": "T",
            "publication_year": 2021,
            "doi": "https://doi.org/10.5/abc",
        }]}
    out = await _fetch_refs_metadata(_f, ["W999"])
    assert out[0]["doi"] == "10.5/abc"
    assert out[0]["openalex_id"] == "W999"
    assert out[0]["year"] == 2021


@pytest.mark.skipif(
    os.environ.get("PAPERAGENT_RUN_NETWORK_TESTS") != "1",
    reason="network test, opt-in via PAPERAGENT_RUN_NETWORK_TESTS=1",
)
@pytest.mark.asyncio
async def test_citation_expand_real_openalex_smoke():
    from app.services.retrieval._http import fetch_with_timeout
    raw = {
        "arxiv": [{"title": "CLIP", "arxiv_id": "2103.00020"}],
    }
    pool = CandidatePool()
    added = await citation_expand(raw, pool, fetch=fetch_with_timeout)
    assert added > 0
