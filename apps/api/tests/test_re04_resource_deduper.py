"""Re04 SOP §5 Task 5 acceptance — resource deduper + ranking tests."""
from __future__ import annotations

import pytest

from app.services.agents.resource_deduper import (
    TIER_ORDER,
    apply_relevance_gate,
    dedup_candidates,
    dedup_key,
    group_by_provenance,
    rank_candidates,
)


def _arxiv_hit(title, arxiv_id, year=2023, cc=10, source="arxiv"):
    return {
        "title": title, "arxiv_id": arxiv_id, "year": year,
        "citation_count": cc, "source": source, "source_query": "Q1",
    }


def _openalex_hit(title, doi, year=2023, cc=20, source="openalex"):
    return {
        "title": title, "doi": doi, "year": year,
        "citation_count": cc, "source": source, "source_query": "Q2",
    }


def _s2_hit(title, paper_id, doi=None, arxiv_id=None, year=2023, cc=15, source="semantic_scholar"):
    h = {"title": title, "paper_id": paper_id, "year": year,
         "citation_count": cc, "source": source, "source_query": "Q3"}
    if doi:
        h["doi"] = doi
    if arxiv_id:
        h["arxiv_id"] = arxiv_id
    return h


# ---------- dedup_key ----------

def test_dedup_key_doi_wins():
    a = {"doi": "10.1109/icip51287.2024.10647726", "arxiv_id": "2103.00020"}
    assert dedup_key(a) == "doi:10.1109/icip51287.2024.10647726"


def test_dedup_key_strips_url_prefix():
    assert dedup_key({"doi": "https://doi.org/10.1234/ABC"}) == "doi:10.1234/abc"
    assert dedup_key({"doi": "DOI:10.1234/abc"}) == "doi:10.1234/abc"


def test_dedup_key_arxiv_fallback():
    assert dedup_key({"arxiv_id": "2103.00020"}) == "arxiv:2103.00020"
    assert dedup_key({"url": "https://arxiv.org/abs/2103.00020v2"}) == "arxiv:2103.00020"
    assert dedup_key({"url": "https://arxiv.org/abs/cs/0102034"}) == "arxiv:cs/0102034"


def test_dedup_key_title_fallback():
    k = dedup_key({"title": "U-Net Steel Crack Segmentation"})
    assert k.startswith("title:") and "u net" in k
    assert "crack" in k


def test_dedup_key_no_identity_returns_none():
    assert dedup_key({}) is None
    assert dedup_key({"title": ""}) is None


# ---------- dedup_candidates ----------

def test_dedup_collapses_same_paper_from_three_sources():
    """Same paper from arxiv + openalex + semantic_scholar → 1 candidate."""
    raw = [
        _arxiv_hit("MVCrackViT paper", "2103.00020", cc=10),
        _openalex_hit("MVCrackViT paper (alt title)", doi="10.1109/X.2024.12345", cc=25),
        _s2_hit("MVCrackViT", paper_id="s2-abc", doi="10.1109/X.2024.12345", arxiv_id="2103.00020", cc=15),
    ]
    out = dedup_candidates(raw)
    assert len(out) == 1
    rec = out[0]
    # Sources merged
    assert set(rec["sources"]) == {"arxiv", "openalex", "semantic_scholar"}
    # Citation count = max across sources
    assert rec["citation_count"] == 25
    # Key won by DOI
    assert rec["dedup_key"].startswith("doi:")


def test_dedup_keeps_distinct_papers_separate():
    raw = [
        _arxiv_hit("Paper A", "2103.00020"),
        _arxiv_hit("Paper B", "2104.11111"),
        _openalex_hit("Paper C", doi="10.1/aaa"),
    ]
    out = dedup_candidates(raw)
    assert len(out) == 3


def test_dedup_preserves_input_order():
    raw = [
        _arxiv_hit("Z paper", "2103.00020"),
        _openalex_hit("A paper", doi="10.1/aaa"),
        _arxiv_hit("M paper", "2104.00001"),
    ]
    out = dedup_candidates(raw)
    titles = [r["title"] for r in out]
    assert titles == ["Z paper", "A paper", "M paper"]


def test_dedup_unkeyed_uses_title_similarity():
    raw = [
        {"title": "U-Net Steel Crack Segmentation", "source": "openalex", "citation_count": 5},
        {"title": "U-Net steel crack  segmentation.", "source": "crossref", "citation_count": 8},
    ]
    out = dedup_candidates(raw)
    # Above the 0.85 threshold; should merge
    assert len(out) == 1
    assert out[0]["citation_count"] == 8


def test_dedup_unkeyed_below_threshold_keeps_separate():
    raw = [
        {"title": "U-Net Steel Crack Segmentation", "source": "openalex"},
        {"title": "BERT for Sentiment Classification", "source": "crossref"},
    ]
    out = dedup_candidates(raw)
    assert len(out) == 2


def test_dedup_merges_source_query_and_round_provenance():
    raw = [
        {**_arxiv_hit("P", "2103.00020", source="arxiv"), "source_query": "Q1", "source_round": 1},
        {**_s2_hit("P", paper_id="s2-abc", arxiv_id="2103.00020", source="semantic_scholar"),
         "source_query": "Q4", "source_round": 4},
    ]
    out = dedup_candidates(raw)
    assert len(out) == 1
    assert set(out[0]["sources"]) == {"arxiv", "semantic_scholar"}
    assert "Q1" in out[0]["queries"]
    assert "Q4" in out[0]["queries"]
    assert sorted(out[0]["rounds"]) == [1, 4]


# ---------- rank_candidates ----------

def test_rank_prefers_lower_tier():
    cands = [
        {"title": "B", "role_hint": "rejected", "citation_count": 1000, "year": 2020},
        {"title": "A", "role_hint": "core", "citation_count": 5, "year": 2024},
        {"title": "C", "role_hint": "candidate", "citation_count": 50, "year": 2023},
    ]
    out = rank_candidates(cands)
    assert [c["title"] for c in out] == ["A", "C", "B"]


def test_rank_within_tier_prefers_citation_then_year():
    cands = [
        {"title": "old_high_cit", "role_hint": "core", "citation_count": 100, "year": 2018},
        {"title": "new_low_cit", "role_hint": "core", "citation_count": 10, "year": 2024},
        {"title": "new_mid_cit", "role_hint": "core", "citation_count": 50, "year": 2024},
    ]
    out = rank_candidates(cands)
    assert [c["title"] for c in out] == ["new_mid_cit", "new_low_cit", "old_high_cit"]


def test_rank_gate_keeps_low_tier_visible_but_pushed_to_end():
    """SOP: off-topic high-citation papers cannot leapfrog the gate."""
    cands = [
        {"title": "A", "role_hint": "core", "citation_count": 5, "year": 2024},
        {"title": "B", "role_hint": "rejected", "citation_count": 9999, "year": 2010},
    ]
    out = rank_candidates(cands, gate_tier="candidate")
    assert out[0]["title"] == "A"
    assert out[1]["title"] == "B"


# ---------- apply_relevance_gate ----------

def test_relevance_gate_rejected_drops_nothing():
    cands = [
        {"title": "A", "role_hint": "rejected"},
        {"title": "B", "role_hint": "core"},
    ]
    assert len(apply_relevance_gate(cands, min_tier="rejected")) == 2


def test_relevance_gate_candidate_drops_long_tail():
    cands = [
        {"title": "A", "role_hint": "core"},
        {"title": "B", "role_hint": "candidate"},
        {"title": "C", "role_hint": "long_tail"},
        {"title": "D", "role_hint": "needs_manual"},
        {"title": "E", "role_hint": "rejected"},
    ]
    out = apply_relevance_gate(cands, min_tier="candidate")
    titles = [c["title"] for c in out]
    assert sorted(titles) == ["A", "B"]


# ---------- group_by_provenance ----------

def test_group_by_provenance():
    raw = [
        _arxiv_hit("P1", "2103.00020", source="arxiv"),
        _s2_hit("P1", paper_id="s2-1", arxiv_id="2103.00020", source="semantic_scholar"),
        _openalex_hit("P2", doi="10.1/aaa", source="openalex"),
    ]
    deduped = dedup_candidates(raw)
    g = group_by_provenance(deduped)
    assert g["arxiv"] == 1
    assert g["semantic_scholar"] == 1
    assert g["openalex"] == 1


# ---------- TIER_ORDER sanity ----------

def test_tier_order_core_lowest_rejected_highest():
    assert TIER_ORDER["core"] < TIER_ORDER["candidate"]
    assert TIER_ORDER["candidate"] < TIER_ORDER["long_tail"]
    assert TIER_ORDER["long_tail"] < TIER_ORDER["rejected"]


def test_dedup_preserves_longest_abstract():
    raw = [
        {**_arxiv_hit("P", "2103.00020", source="arxiv"),
         "abstract": "short"},
        {**_s2_hit("P", paper_id="s2-1", arxiv_id="2103.00020", source="semantic_scholar"),
         "abstract": "this is a much longer abstract with many words describing the paper"},
    ]
    out = dedup_candidates(raw)
    assert "much longer" in out[0]["abstract"]
