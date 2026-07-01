"""Re02 CandidatePool tests (apps/api/app/services/agents/candidate_pool).

Covers:
1. add_paper dedup merges sources
2. add_repo keeps quoted_paper_titles
3. collect_papers_from_raw handles arxiv/openalex/crossref
4. collect_repos_from_raw extracts quoted paper titles from GitHub and adds them as paper candidates
5. collect_mentioned_datasets only adds names that appear in the raw blob (no fabrication)
6. stats() returns {paper, dataset, repo} counts
"""

from __future__ import annotations

import pytest

from app.services.agents.candidate_pool import (
    CandidatePool,
    collect_mentioned_datasets,
    collect_papers_from_raw,
    collect_repos_from_raw,
)


pytestmark = pytest.mark.re02


def test_add_paper_dedup_merges_sources():
    pool = CandidatePool()
    pool.add_paper(title="Deep Residual Learning", source="arxiv")
    pool.add_paper(title="Deep Residual Learning", source="openalex")
    pool.add_paper(title="deep residual learning", source="crossref")
    rows = pool.by_evidence_type("paper")
    assert len(rows) == 1
    assert set(rows[0].sources) == {"arxiv", "openalex", "crossref"}


def test_add_repo_keeps_quoted_paper_titles():
    pool = CandidatePool()
    quoted = ["Paper A on Wavelet Denoising for Underwater Acoustic Signals"]
    pool.add_repo(
        full_name="me/underwater",
        source="github",
        url="https://github.com/me/underwater",
        description=f"Implementation of \"{quoted[0]}\"",
        quoted_paper_titles=quoted,
    )
    rows = pool.by_evidence_type("repo")
    assert len(rows) == 1
    assert rows[0].quoted_paper_titles == quoted


def test_collect_papers_from_raw_handles_all_adapters():
    pool = CandidatePool()
    raw = {
        "arxiv":   [{"title": "Arxiv Paper X", "year": 2022, "url": "https://x", "abstract": "abs"}],
        "openalex":[{"title": "OpenAlex Paper Y", "publication_year": 2021, "DOI": "10.1/y"}],
        "crossref":[{"title": "Crossref Paper Z", "issued": "2020", "URL": "https://z"}],
    }
    n = collect_papers_from_raw(raw, pool)
    assert n == 3
    titles = {c.title for c in pool.by_evidence_type("paper")}
    assert titles == {"Arxiv Paper X", "OpenAlex Paper Y", "Crossref Paper Z"}


def test_collect_repos_from_raw_extracts_quoted_titles_as_papers():
    pool = CandidatePool()
    raw = {
        "github": [
            {
                "full_name": "zakaria76al/USC",
                "html_url": "https://github.com/zakaria76al/USC",
                "description": 'The paper "A spatio-temporal deep learning approach for underwater acoustic signals classification"',
                "language": "Python",
            }
        ]
    }
    n = collect_repos_from_raw(raw, pool)
    assert n == 1
    repo_rows = pool.by_evidence_type("repo")
    paper_rows = pool.by_evidence_type("paper")
    assert len(repo_rows) == 1
    assert any("spatio-temporal deep learning" in p.title for p in paper_rows)


def test_collect_mentioned_datasets_does_not_fabricate():
    pool = CandidatePool()
    raw = {
        "arxiv": [
            {"title": "Underwater acoustic target recognition on the ShipsEar dataset",
             "abstract": "We evaluate on ShipsEar and DeepShip."},
        ]
    }
    whitelist = {"signal_timeseries": ("ShipsEar", "DeepShip", "SonAIr")}
    n = collect_mentioned_datasets(raw, pool, whitelist=whitelist)
    titles = {c.title for c in pool.by_evidence_type("dataset")}
    assert "ShipsEar" in titles
    assert "DeepShip" in titles
    assert "SonAIr" not in titles
    assert n == 2


def test_stats_returns_paper_dataset_repo_counts():
    pool = CandidatePool()
    pool.add_paper(title="Paper A", source="arxiv")
    pool.add_paper(title="Paper B", source="openalex")
    pool.add_repo(full_name="me/repo")
    pool.add_dataset(name="DTU", source="whitelist")
    s = pool.stats()
    assert s.get("paper") == 2
    assert s.get("repo") == 1
    assert s.get("dataset") == 1
