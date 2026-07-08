"""Loop 2: Citation Expander unit test — seed selection, dedup, concurrent expansion."""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.citation_expander import (
    citation_expander_node,
    _select_seeds,
    _dedup,
    _normalize_title,
    _identify_surveys,
    _extract_repos,
)


SAMPLE_VERIFIED = [
    {
        "title": "YOLOv5: Real-time Object Detection",
        "hit_keywords": ["YOLOv5", "detection"],
        "relation_to_topic": "baseline",
        "paper_id": "abc123",
        "doi": "10.1109/CVPR.2020.123",
        "arxiv_id": "2104.12345",
        "citation_count": 500,
    },
    {
        "title": "Some Irrelevant Paper",
        "hit_keywords": [],
        "relation_to_topic": "none",
        # No identifiers — should be skipped
    },
    {
        "title": "HIC-YOLOv5: Improved YOLOv5 For Small Object Detection",
        "hit_keywords": ["YOLOv5", "small object"],
        "relation_to_topic": "parallel",
        "paper_id": "def456",
        "doi": None,
        "arxiv_id": "2201.67890",
        "citation_count": 50,
    },
]

TOPIC_ATOMS = {
    "method": ["YOLOv5"],
    "object": ["steel defect"],
    "task": ["detection"],
}


def test_select_seeds_picks_most_relevant():
    seeds = _select_seeds(SAMPLE_VERIFIED, TOPIC_ATOMS, top_n=5)
    assert len(seeds) == 2  # only 2 have identifiers
    # YOLOv5 paper should be top (more hit_keywords overlap + baseline)
    assert "YOLOv5" in seeds[0]["title"]
    assert seeds[0].get("relevance_score", 0) >= seeds[1].get("relevance_score", 0)


def test_select_seeds_skips_no_id():
    seeds = _select_seeds(SAMPLE_VERIFIED, TOPIC_ATOMS, top_n=5)
    for s in seeds:
        assert s.get("paper_id") or s.get("doi") or s.get("arxiv_id"), \
            "Seed without identifier was selected"


def test_select_seeds_top_n_limit():
    seeds = _select_seeds(SAMPLE_VERIFIED, TOPIC_ATOMS, top_n=1)
    assert len(seeds) == 1


def test_select_seeds_has_selection_reason():
    seeds = _select_seeds(SAMPLE_VERIFIED, TOPIC_ATOMS, top_n=5)
    for s in seeds:
        assert "seed_selection_reason" in s
        assert "relevance_score" in s


def test_dedup_removes_duplicates():
    papers = [
        {"title": "Paper A", "paper_id": "pid1", "doi": "10.1/a"},
        {"title": "Paper A (duplicate)", "paper_id": "pid1", "doi": "10.1/b"},
        {"title": "Paper B", "paper_id": "pid2", "doi": "10.2/b"},
    ]
    result = _dedup(papers, set())
    assert len(result) == 2  # pid1 deduped


def test_dedup_removes_existing_titles():
    papers = [
        {"title": "Existing Paper", "paper_id": "new1"},
        {"title": "New Paper", "paper_id": "new2"},
    ]
    existing = {_normalize_title("Existing Paper")}
    result = _dedup(papers, existing)
    assert len(result) == 1
    assert "New" in result[0]["title"]


def test_normalize_title():
    assert _normalize_title("  Hello   World  ") == "hello world"
    assert _normalize_title("ABC") == "abc"


def test_identify_surveys():
    papers = [
        {"title": "A Survey of Deep Learning", "paper_id": "s1"},
        {"title": "YOLOv5: Detection", "paper_id": "s2"},
        {"title": "Systematic Review of CNNs", "paper_id": "s3"},
        {"title": "Regular Paper", "paper_id": "s4"},
    ]
    surveys = _identify_surveys(papers)
    assert len(surveys) == 2
    survey_titles = [s["title"] for s in surveys]
    assert "A Survey of Deep Learning" in survey_titles
    assert "Systematic Review of CNNs" in survey_titles


def test_extract_repos():
    papers = [
        {"title": "Paper A", "abstract": "Code at https://github.com/user/repo1", "url": ""},
        {"title": "Paper B", "abstract": "No code link", "url": "https://github.com/user/repo2"},
    ]
    repos = _extract_repos(papers)
    assert len(repos) >= 1
    repo_urls = [r["url"] for r in repos]
    assert any("github.com/user/repo1" in u for u in repo_urls)


def test_citation_expander_node_with_mocked_s2():
    """Test full node with mocked S2 API."""
    mock_refs = [
        {"title": "Referenced Paper 1", "paper_id": "ref1", "doi": "10.1/r1", "url": "http://example.com"},
        {"title": "A Survey of Detection Methods", "paper_id": "ref2", "doi": None, "url": ""},
    ]
    mock_cits = [
        {"title": "Citing Paper 1", "paper_id": "cit1", "doi": "10.1/c1", "url": ""},
    ]

    state = {
        "verified_papers": SAMPLE_VERIFIED,
        "topic_atoms": TOPIC_ATOMS,
        "trace_events": [],
    }

    async def mock_refs_fn(*args, **kwargs):
        return mock_refs

    async def mock_cits_fn(*args, **kwargs):
        return mock_cits

    with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_references",
               side_effect=mock_refs_fn):
        with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_citations",
                   side_effect=mock_cits_fn):
            result = citation_expander_node(state)

    assert result["citation_expansion_done"] is True
    assert len(result["seed_papers"]) == 2
    assert len(result["expanded_papers"]) >= 1
    # Each expanded paper has expanded_from_seed
    for p in result["expanded_papers"]:
        assert "expanded_from_seed" in p


def test_citation_expander_no_seeds():
    """When no seeds have identifiers, expansion is skipped gracefully."""
    state = {
        "verified_papers": [{"title": "No ID Paper", "hit_keywords": []}],
        "topic_atoms": {},
        "trace_events": [],
    }
    result = citation_expander_node(state)
    assert result["citation_expansion_done"] is True
    assert len(result["expanded_papers"]) == 0
    assert len(result["seed_papers"]) == 0


def test_citation_expander_s2_failure_graceful():
    """S2 API failure should not crash the pipeline."""
    state = {
        "verified_papers": SAMPLE_VERIFIED,
        "topic_atoms": TOPIC_ATOMS,
        "trace_events": [],
    }

    async def mock_fail(*args, **kwargs):
        raise Exception("S2 API down")

    with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_references",
               side_effect=mock_fail):
        with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_citations",
                   side_effect=mock_fail):
            result = citation_expander_node(state)

    # Should not crash, should have empty expansion
    assert result["citation_expansion_done"] is True


def test_citation_expander_trace_recorded():
    """Trace should record per-seed expansion info."""
    state = {
        "verified_papers": SAMPLE_VERIFIED,
        "topic_atoms": TOPIC_ATOMS,
        "trace_events": [],
    }

    async def mock_refs(*args, **kwargs):
        return [{"title": "Ref", "paper_id": "r1"}]

    async def mock_cits(*args, **kwargs):
        return [{"title": "Cit", "paper_id": "c1"}]

    with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_references",
               side_effect=mock_refs):
        with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_citations",
                   side_effect=mock_cits):
            result = citation_expander_node(state)

    traces = result["trace_events"]
    assert len(traces) == 1
    assert traces[0]["node"] == "citation_expander"
    assert "per_seed" in traces[0]
