"""Re8.2 Seed Repair 2.0 tests.

Covers the WP2 deterministic pieces:
  - SeedCandidate factory and source normalisation
  - title normalisation, query-variant building, acronym alias handling
  - multi-source deduplication + conflict tagging
  - structured scoring (title/author/year/abstract/identifier)
  - threshold logic (Plan A + Plan B conservative)
  - LLM disambiguation gating and parsing
  - _fetch_seed_candidates orchestration with mocked adapters
  - xlm_r S1 BERT alias and yolo_steel S2 author/year disambiguation
"""
from __future__ import annotations

import importlib

import pytest
from unittest.mock import AsyncMock

from apps.api.app.services.agents.graph.re80_schema import (
    SEED_AUDIT_REASON_CODES,
    make_seed_candidate,
)
from apps.api.app.services.agents.graph.nodes.seed_resolver import (
    _apply_threshold,
    _build_query_variants,
    _compute_structured_scores,
    _deduplicate_candidates,
    _extract_core_terms,
    _fetch_seed_candidates,
    _generate_acronym_aliases,
    _llm_disambiguate,
    _normalize_candidate_title,
    _normalize_title_for_query,
    _remove_punctuation,
    _resolve_confidence_to_string,
    _should_llm_disambiguate,
    _source_result_to_candidate,
    _strip_subtitle,
    _titles_agree,
)


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

class TestMakeSeedCandidate:
    def test_defaults_are_safe(self):
        c = make_seed_candidate()
        assert c["title"] == ""
        assert c["authors"] == []
        assert c["sources"] == []
        assert c["conflicts"] == []
        assert c["total_score"] == 0.0

    def test_explicit_values_preserved(self):
        c = make_seed_candidate(
            title="BERT",
            authors=["Devlin J."],
            year=2019,
            doi="10.18653/v1/N19-1423",
            sources=["crossref"],
            total_score=0.92,
            confidence="verified",
        )
        assert c["title"] == "BERT"
        assert c["year"] == 2019
        assert c["doi"] == "10.18653/v1/N19-1423"
        assert c["confidence"] == "verified"


# ---------------------------------------------------------------------------
# Title normalisation and query variants
# ---------------------------------------------------------------------------

class TestTitleNormalisation:
    def test_normalize_title_lowercase_and_whitespace(self):
        assert _normalize_title_for_query("  An   Image  ") == "an image"

    def test_strip_subtitle_removes_colon_suffix(self):
        t = "BERT: Pre-training of Deep Bidirectional Transformers"
        # _strip_subtitle keeps only the main title before the colon
        assert _strip_subtitle(t) == "bert"

    def test_strip_subtitle_no_separator_returns_full(self):
        t = "Deep Residual Learning for Image Recognition"
        assert _strip_subtitle(t) == "deep residual learning for image recognition"

    def test_remove_punctuation_collapses_no_space(self):
        # Hyphens are removed and the surrounding characters collapse
        assert _remove_punctuation("a. b-c, d!") == "a bc d"

    def test_extract_core_terms_drops_stopwords(self):
        terms = _extract_core_terms("A New Method for Object Detection")
        assert "method" in terms
        assert "object" in terms
        assert "detection" in terms
        assert "a" not in terms
        assert "for" not in terms

    def test_generate_acronym_aliases_known_map(self):
        aliases = _generate_acronym_aliases(
            "Bidirectional Encoder Representations from Transformers"
        )
        assert "bert" in aliases

    def test_generate_acronym_aliases_word_initial(self):
        aliases = _generate_acronym_aliases("You Only Look Once Object Detection")
        # Word-initial acronym for >=3 word titles
        assert any(a.startswith("yolo") for a in aliases)

    def test_build_query_variants_all_four(self):
        queries = _build_query_variants(
            "BERT: Pre-training of Deep Bidirectional Transformers",
            authors=["Jacob Devlin", "Ming-Wei Chang"],
            year=2019,
        )
        assert len(queries) >= 2
        # full title present (keep the hyphenated form as returned by the API)
        assert any("pre-training" in q.lower() for q in queries)
        # stripped subtitle present
        assert any(q.lower().strip() == "bert" for q in queries)
        # author + core terms
        assert any("devlin" in q.lower() and "bert" in q.lower() for q in queries)
        # year + core terms
        assert any("2019" in q and "bert" in q.lower() for q in queries)


# ---------------------------------------------------------------------------
# Source normalisation and deduplication
# ---------------------------------------------------------------------------

class TestSourceNormalisation:
    def test_crossref_result_to_candidate(self):
        raw = {"title": "T", "authors": ["A"], "year": 2020, "doi": "10.1/x", "url": "http://x"}
        c = _source_result_to_candidate("crossref", raw)
        assert c["doi"] == "10.1/x"
        assert c["canonical_url"] == "http://x"
        assert c["sources"] == ["crossref"]

    def test_arxiv_result_to_candidate(self):
        raw = {"title": "T", "authors": ["A"], "year": 2020, "arxiv_id": "2001.00001", "url": "http://arxiv.org/abs/2001.00001"}
        c = _source_result_to_candidate("arxiv", raw)
        assert c["arxiv_id"] == "2001.00001"
        assert c["sources"] == ["arxiv"]

    def test_openalex_doi_stripped(self):
        raw = {"title": "T", "authorships": [{"author": {"display_name": "A B"}}], "doi": "https://doi.org/10.1/x"}
        c = _source_result_to_candidate("openalex", raw)
        assert c["doi"] == "10.1/x"

    def test_deduplicate_candidates_merges_sources_by_doi(self):
        a = make_seed_candidate(title="T", doi="10.12345/x", sources=["crossref"])
        b = make_seed_candidate(title="T", doi="10.12345/x", sources=["semantic_scholar"])
        merged = _deduplicate_candidates([a, b])
        assert len(merged) == 1
        assert set(merged[0]["sources"]) == {"crossref", "semantic_scholar"}

    def test_deduplicate_candidates_tags_title_conflict(self):
        a = make_seed_candidate(title="T", sources=["crossref"])
        b = make_seed_candidate(title="T", sources=["semantic_scholar"])
        merged = _deduplicate_candidates([a, b])
        assert len(merged) == 2
        assert all(c.get("conflict") for c in merged)


# ---------------------------------------------------------------------------
# Structured scoring and thresholds
# ---------------------------------------------------------------------------

class TestStructuredScoring:
    def test_exact_title_and_doi_scores(self):
        cand = make_seed_candidate(
            title="BERT: Pre-training of Deep Bidirectional Transformers",
            authors=["Jacob Devlin", "Ming-Wei Chang"],
            year=2019,
            doi="10.18653/v1/N19-1423",
        )
        scores = _compute_structured_scores(
            "BERT: Pre-training of Deep Bidirectional Transformers",
            ["Devlin, J.", "Chang, M."],
            2019,
            cand,
        )
        assert scores["title_score"] == pytest.approx(1.0, abs=0.01)
        assert scores["author_score"] == pytest.approx(1.0, abs=0.01)
        assert scores["year_score"] == 1.0
        assert scores["identifier_score"] == 1.0

    def test_author_score_partial_overlap(self):
        cand = make_seed_candidate(title="T", authors=["Devlin"])
        scores = _compute_structured_scores("T", ["Devlin", "Chang"], None, cand)
        assert 0.0 < scores["author_score"] < 1.0

    def test_year_score_penalises_large_delta(self):
        cand = make_seed_candidate(title="T", year=2010)
        scores = _compute_structured_scores("T", [], 2020, cand)
        assert scores["year_score"] < 1.0

    def test_identifier_score_arxiv_less_than_doi(self):
        doi_cand = make_seed_candidate(title="T", doi="10.12345/x")
        arx_cand = make_seed_candidate(title="T", arxiv_id="2001.00001")
        assert _compute_structured_scores("T", [], None, doi_cand)["identifier_score"] == 1.0
        assert _compute_structured_scores("T", [], None, arx_cand)["identifier_score"] == 0.8

    def test_abstract_score_partial_credit_when_candidate_has_abstract(self):
        cand = make_seed_candidate(title="T", abstract="a b c d e")
        scores = _compute_structured_scores("T", [], None, cand)
        assert scores["abstract_score"] == 0.3


class TestApplyThreshold:
    def test_plan_a_verified(self):
        scores = {
            "title_score": 1.0,
            "author_score": 1.0,
            "year_score": 1.0,
            "abstract_score": 0.3,
            "identifier_score": 1.0,
        }
        conf, total = _apply_threshold(scores)
        assert conf == "verified"
        assert total >= 0.85

    def test_plan_a_ambiguous(self):
        scores = {
            "title_score": 0.95,
            "author_score": 0.85,
            "year_score": 0.8,
            "abstract_score": 0.3,
            "identifier_score": 0.0,
        }
        conf, total = _apply_threshold(scores)
        assert conf == "ambiguous"
        assert 0.70 <= total < 0.85

    def test_plan_a_not_found(self):
        scores = {
            "title_score": 0.3,
            "author_score": 0.0,
            "year_score": 0.0,
            "abstract_score": 0.0,
            "identifier_score": 0.0,
        }
        conf, total = _apply_threshold(scores)
        assert conf == "not_found"

    def test_plan_b_downgrades_without_author_or_identifier(self):
        scores = {
            "title_score": 0.95,
            "author_score": 0.0,
            "year_score": 1.0,
            "abstract_score": 1.0,
            "identifier_score": 0.8,
        }
        conf, total = _apply_threshold(scores, use_plan_b=True)
        # Plan B requires (title>=0.88 AND author>=0.70) OR identifier==1.0
        # None hold, so even a decent total stays ambiguous
        assert conf == "ambiguous"

    def test_plan_b_verified_when_identifier_perfect(self):
        scores = {
            "title_score": 0.5,
            "author_score": 0.0,
            "year_score": 0.0,
            "abstract_score": 0.0,
            "identifier_score": 1.0,
        }
        conf, _ = _apply_threshold(scores, use_plan_b=True)
        assert conf == "verified"

    def test_resolve_confidence_to_string(self):
        assert _resolve_confidence_to_string("verified") == "high"
        assert _resolve_confidence_to_string("ambiguous") == "medium"
        assert _resolve_confidence_to_string("not_found") == "low"


# ---------------------------------------------------------------------------
# LLM disambiguation gating and parsing
# ---------------------------------------------------------------------------

class TestShouldLLMDisambiguate:
    def _cand(self, total: float) -> dict:
        return make_seed_candidate(total_score=total, confidence="ambiguous")

    def test_true_when_close_and_in_range(self):
        assert _should_llm_disambiguate([self._cand(0.85), self._cand(0.79)])

    def test_false_when_only_one_candidate(self):
        assert not _should_llm_disambiguate([self._cand(0.85)])

    def test_false_when_too_many_candidates(self):
        assert not _should_llm_disambiguate([self._cand(0.85)] * 6)

    def test_false_when_gap_too_large(self):
        assert not _should_llm_disambiguate([self._cand(0.95), self._cand(0.80)])

    def test_false_when_scores_too_low(self):
        assert not _should_llm_disambiguate([self._cand(0.60), self._cand(0.55)])


class TestLLMDisambiguate:
    _LLM_TARGET = "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation"

    @pytest.mark.asyncio
    async def test_selects_candidate(self, monkeypatch):
        cands = [make_seed_candidate(title="A"), make_seed_candidate(title="B")]
        monkeypatch.setattr(
            self._LLM_TARGET,
            lambda *args, **kwargs: {"selected_index": 1, "confidence": "high", "reason": "B matches", "reject_all": False},
        )
        selected = await _llm_disambiguate("T", [], None, cands)
        assert selected is not None
        assert selected["title"] == "B"
        assert selected["_disambiguation"]["selected_index"] == 1

    @pytest.mark.asyncio
    async def test_reject_all_returns_none(self, monkeypatch):
        cands = [make_seed_candidate(title="A"), make_seed_candidate(title="B")]
        monkeypatch.setattr(
            self._LLM_TARGET,
            lambda *args, **kwargs: {"selected_index": 0, "confidence": "high", "reason": "", "reject_all": True},
        )
        assert await _llm_disambiguate("T", [], None, cands) is None

    @pytest.mark.asyncio
    async def test_low_confidence_returns_none(self, monkeypatch):
        cands = [make_seed_candidate(title="A")]
        monkeypatch.setattr(
            self._LLM_TARGET,
            lambda *args, **kwargs: {"selected_index": 0, "confidence": "low", "reason": "", "reject_all": False},
        )
        assert await _llm_disambiguate("T", [], None, cands) is None

    @pytest.mark.asyncio
    async def test_out_of_range_index_returns_none(self, monkeypatch):
        cands = [make_seed_candidate(title="A")]
        monkeypatch.setattr(
            self._LLM_TARGET,
            lambda *args, **kwargs: {"selected_index": 5, "confidence": "high", "reason": "", "reject_all": False},
        )
        assert await _llm_disambiguate("T", [], None, cands) is None

    @pytest.mark.asyncio
    async def test_legacy_selection_field_fallback(self, monkeypatch):
        cands = [make_seed_candidate(title="A"), make_seed_candidate(title="B")]
        monkeypatch.setattr(
            self._LLM_TARGET,
            lambda *args, **kwargs: {"selection": 0, "confidence": "high", "reason": ""},
        )
        selected = await _llm_disambiguate("T", [], None, cands)
        assert selected["title"] == "A"


# ---------------------------------------------------------------------------
# _fetch_seed_candidates orchestration
# ---------------------------------------------------------------------------

def _mock_adapters(monkeypatch, crossref=None, s2=None, oa=None, arxiv=None):
    async def _crossref(*args, **kwargs):
        return list(crossref or [])

    async def _s2(*args, **kwargs):
        return list(s2 or [])

    async def _oa(*args, **kwargs):
        return list(oa or [])

    async def _arxiv(*args, **kwargs):
        return list(arxiv or [])

    # Patch the actual adapter module objects so that local imports inside
    # ``seed_resolver._fetch_seed_candidates`` pick up the mocks at call time.
    crossref_mod = importlib.import_module(
        "apps.api.app.services.retrieval.adapters.crossref_search"
    )
    s2_mod = importlib.import_module(
        "apps.api.app.services.retrieval.adapters.semantic_scholar_search"
    )
    oa_mod = importlib.import_module(
        "apps.api.app.services.retrieval.adapters.openalex_search"
    )
    arxiv_mod = importlib.import_module(
        "apps.api.app.services.retrieval.adapters.arxiv_search"
    )
    monkeypatch.setattr(crossref_mod, "crossref_search", _crossref)
    monkeypatch.setattr(s2_mod, "semantic_scholar_search", _s2)
    monkeypatch.setattr(oa_mod, "openalex_search", _oa)
    monkeypatch.setattr(arxiv_mod, "arxiv_search", _arxiv)


class TestFetchSeedCandidates:
    @pytest.mark.asyncio
    async def test_no_results_returns_none(self, monkeypatch):
        _mock_adapters(monkeypatch)
        assert await _fetch_seed_candidates("Nonexistent Paper Title") is None

    @pytest.mark.asyncio
    async def test_single_hit_normalised_and_scored(self, monkeypatch):
        _mock_adapters(
            monkeypatch,
            crossref=[{"title": "BERT: Pre-training of Deep Bidirectional Transformers",
                       "authors": ["Devlin", "Chang"], "year": 2019, "doi": "10.18653/v1/N19-1423"}],
        )
        best = await _fetch_seed_candidates(
            "BERT: Pre-training of Deep Bidirectional Transformers",
            authors=["Devlin", "Chang"],
            year=2019,
        )
        assert best is not None
        assert "total_score" in best
        assert best["confidence"] == "verified"
        assert best["doi"] == "10.18653/v1/N19-1423"
        assert "all_candidates" in best

    @pytest.mark.asyncio
    async def test_multi_source_doi_merge(self, monkeypatch):
        _mock_adapters(
            monkeypatch,
            crossref=[{"title": "BERT", "authors": ["Devlin"], "year": 2019, "doi": "10.12345/x"}],
            s2=[{"title": "BERT", "authors": ["Devlin", "Chang"], "year": 2019, "doi": "10.12345/x"}],
        )
        best = await _fetch_seed_candidates("BERT", authors=["Devlin"], year=2019)
        assert best is not None
        assert set(best["sources"]) == {"crossref", "semantic_scholar"}
        assert "Chang" in best["authors"]

    @pytest.mark.asyncio
    async def test_conflict_tagged_when_same_title_no_doi(self, monkeypatch):
        _mock_adapters(
            monkeypatch,
            crossref=[{"title": "Foo Bar", "authors": ["A"], "year": 2020}],
            s2=[{"title": "Foo Bar", "authors": ["A"], "year": 2020}],
        )
        best = await _fetch_seed_candidates("Foo Bar", authors=["A"], year=2020)
        assert best is not None
        # at least one candidate should be conflict-tagged
        assert any(c.get("conflict") for c in best["all_candidates"])

    @pytest.mark.asyncio
    async def test_llm_disambiguation_promotes_selected(self, monkeypatch):
        # Two close no-DOI candidates stay close and trigger LLM.
        # Force a single query variant so crossref + s2 yield exactly two
        # candidates and the LLM disambiguation guard fires.
        _mock_adapters(
            monkeypatch,
            crossref=[{"title": "Foo Bar", "authors": ["A"], "year": 2020}],
            s2=[{"title": "Foo Bar", "authors": ["A"], "year": 2020}],
        )
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._build_query_variants",
            lambda *args, **kwargs: ["Foo Bar"],
        )
        monkeypatch.setattr(
            TestLLMDisambiguate._LLM_TARGET,
            lambda *args, **kwargs: {"selected_index": 1, "confidence": "high", "reason": "second", "reject_all": False},
        )
        best = await _fetch_seed_candidates("Foo Bar", authors=["A"], year=2020)
        assert best is not None
        assert best.get("_disambiguation") is not None
        assert best["_disambiguation"]["selected_index"] == 1

    @pytest.mark.asyncio
    async def test_llm_reject_all_keeps_top_ranked(self, monkeypatch):
        _mock_adapters(
            monkeypatch,
            crossref=[{"title": "Foo Bar", "authors": ["A"], "year": 2020}],
            s2=[{"title": "Foo Bar Baz", "authors": ["A"], "year": 2020}],
        )
        monkeypatch.setattr(
            TestLLMDisambiguate._LLM_TARGET,
            lambda *args, **kwargs: {"selected_index": 0, "confidence": "high", "reason": "", "reject_all": True},
        )
        best = await _fetch_seed_candidates("Foo Bar", authors=["A"], year=2020)
        # reject_all should not crash; best is still returned for downstream audit
        assert best is not None

    @pytest.mark.asyncio
    async def test_xlm_r_bert_alias_verified(self, monkeypatch):
        # xlm_r S1: user supplies the long BERT title; crossref/S2 return it
        _mock_adapters(
            monkeypatch,
            crossref=[{
                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "authors": ["Jacob Devlin", "Ming-Wei Chang", "Kentoon Lee", "Kristina Toutanova"],
                "year": 2019,
                "doi": "10.18653/v1/N19-1423",
            }],
        )
        best = await _fetch_seed_candidates(
            "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            authors=["Jacob Devlin", "Ming-Wei Chang", "Kentoon Lee", "Kristina Toutanova"],
            year=2019,
        )
        assert best is not None
        assert best["confidence"] == "verified"
        assert best["doi"] or best["arxiv_id"]
        assert _titles_agree(best["title"], "BERT")

    @pytest.mark.asyncio
    async def test_yolo_steel_song_yan_disambiguation(self, monkeypatch):
        # yolo_steel S2: title + Song/Yan authors + year
        _mock_adapters(
            monkeypatch,
            crossref=[{
                "title": "Deep Learning for Steel Surface Defect Detection",
                "authors": ["Song", "Yan"],
                "year": 2021,
                "doi": "10.1000/steel",
            }],
        )
        best = await _fetch_seed_candidates(
            "Deep Learning for Steel Surface Defect Detection",
            authors=["Song", "Yan"],
            year=2021,
        )
        assert best is not None
        assert best["confidence"] == "verified"
        assert {"Song", "Yan"} <= {a.split()[-1] for a in best["authors"]}

    @pytest.mark.asyncio
    async def test_year_conflict_demotes_candidate(self, monkeypatch):
        _mock_adapters(
            monkeypatch,
            crossref=[{
                "title": "Attention is All You Need",
                "authors": ["Vaswani"],
                "year": 2017,
                "doi": "10.12345/attn",
            }],
        )
        best = await _fetch_seed_candidates(
            "Attention is All You Need",
            authors=["Vaswani"],
            year=2020,
        )
        assert best is not None
        assert best["year_score"] < 1.0


# ---------------------------------------------------------------------------
# Integration: seed_resolver_node title-only path uses WP2 fallback
# ---------------------------------------------------------------------------

class TestSeedResolverWP2Fallback:
    def test_title_only_seed_uses_fetch_seed_candidates(self, monkeypatch):
        _mock_adapters(
            monkeypatch,
            crossref=[{
                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "authors": ["Devlin", "Chang"],
                "year": 2019,
                "doi": "10.18653/v1/N19-1423",
            }],
        )
        # Force the new WP2 path by disabling the legacy _fetch_by_title path
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_by_title",
            AsyncMock(return_value=None),
        )
        from apps.api.app.services.agents.graph.nodes.seed_resolver import seed_resolver_node
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {
                    "seed_id": "S1",
                    "input_form": "title",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                    "authors": ["Devlin", "Chang"],
                    "year": 2019,
                    "role": "classic_anchor",
                },
            ],
        }
        result = seed_resolver_node(state)
        cards = result["seed_cards"]
        assert len(cards) == 1
        assert cards[0]["existence_status"] == "verified"
        assert cards[0]["doi"] == "10.18653/v1/N19-1423"
        assert "total_score" in cards[0]
        assert len(result["verified_papers"]) == 1


# ---------------------------------------------------------------------------
# Reason-code constants sanity check
# ---------------------------------------------------------------------------

def test_seed_audit_reason_codes_include_required_values():
    required = {
        "SEED_NOT_FOUND",
        "SEED_LOW_CONFIDENCE",
        "SEED_SOURCE_CONFLICT",
        "SEED_AUTHOR_MISMATCH",
        "SEED_YEAR_MISMATCH",
        "SEED_IDENTIFIER_CONFLICT",
        "SEED_FULLTEXT_UNAVAILABLE",
        "SEED_VERIFIED",
    }
    assert required.issubset(set(SEED_AUDIT_REASON_CODES))
