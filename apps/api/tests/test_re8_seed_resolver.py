"""Re8.0 Seed Resolver + Schema Contract Tests.

Tests that the seed_resolver_node correctly audits user-supplied papers
and that fabricated DOIs / hallucinated titles never enter the evidence
pool (verified_papers). This is the core safety contract of Re8.0 §6.2.
"""
from __future__ import annotations

import os

import pytest
from unittest.mock import AsyncMock, patch

from apps.api.app.services.agents.graph.re80_schema import (
    SEED_EXISTENCE_STATUS,
    SEED_INPUT_FORMS,
    SEED_ROLES,
    default_re80_state,
    is_seed_evidence_eligible,
    make_evidence_gap,
    make_ledger_entry,
    make_method_family,
    make_seed_card,
    validate_evidence_gap,
    validate_ledger_entry,
    validate_method_family,
    validate_seed_card,
)
from apps.api.app.services.agents.graph.nodes.seed_resolver import (
    _author_lastname,
    _classify_input,
    _compute_confidence,
    _decide_existence,
    _fetch_by_title,
    _merge_with_conflict_tagging,
    _normalize_seed_payload,
    _normalize_title_hit,
    _title_similarity,
    _titles_agree,
    _year_penalty,
    seed_resolver_node,
)


# ---------------------------------------------------------------------------
# Schema helpers (re80_schema.py)
# ---------------------------------------------------------------------------

class TestMakeSeedCard:
    def test_defaults_are_safe(self):
        card = make_seed_card(seed_id="s1")
        assert card["seed_id"] == "s1"
        assert card["existence_status"] == "ambiguous"
        assert card["fulltext_status"] == "metadata_only"
        assert card["role"] == "unknown"
        assert card["authors"] == []
        assert card["raw_input"] == {}

    def test_verified_card_requires_identifier(self):
        # verified but no title/doi/url → invalid
        card = make_seed_card(seed_id="s1", existence_status="verified")
        errs = validate_seed_card(card)
        assert any("verified seed must have" in e for e in errs)

    def test_verified_card_with_doi_is_valid(self):
        card = make_seed_card(seed_id="s1", existence_status="verified",
                              doi="10.1000/test", resolved_title="Test Paper")
        assert validate_seed_card(card) == []

    def test_invalid_existence_status_rejected(self):
        card = make_seed_card(seed_id="s1", existence_status="bogus")
        errs = validate_seed_card(card)
        assert any("existence_status" in e for e in errs)

    def test_invalid_role_rejected(self):
        card = make_seed_card(seed_id="s1", role="bogus_role")
        errs = validate_seed_card(card)
        assert any("role" in e for e in errs)


class TestIsSeedEvidenceEligible:
    def test_ambiguous_not_eligible(self):
        card = make_seed_card(seed_id="s1", existence_status="ambiguous",
                              resolved_title="T", doi="10.1/x")
        assert not is_seed_evidence_eligible(card)

    def test_verified_with_doi_eligible(self):
        card = make_seed_card(seed_id="s1", existence_status="verified",
                              resolved_title="T", doi="10.1/x")
        assert is_seed_evidence_eligible(card)

    def test_verified_no_identifier_not_eligible(self):
        card = make_seed_card(seed_id="s1", existence_status="verified")
        assert not is_seed_evidence_eligible(card)


class TestMethodFamilyCard:
    def test_valid_card(self):
        card = make_method_family(family_id="f1", name="Transformer")
        assert validate_method_family(card) == []

    def test_invalid_relation(self):
        card = make_method_family(family_id="f1", name="X",
                                  relation_to_seed="bogus")
        assert validate_method_family(card) != []


class TestEvidenceGap:
    def test_valid_gap(self):
        gap = make_evidence_gap(gap_id="g1", question="What is SOTA?")
        assert validate_evidence_gap(gap) == []

    def test_invalid_gap_type(self):
        gap = make_evidence_gap(gap_id="g1", question="Q", gap_type="bogus")
        errs = validate_evidence_gap(gap)
        assert any("gap_type" in e for e in errs)


class TestLedgerEntry:
    def test_confidence_clamped(self):
        entry = make_ledger_entry(
            decision_id="d1", stage="seed_audit", decision="x",
            confidence=5.0,
        )
        assert entry["confidence"] == 1.0

    def test_confidence_negative_clamped(self):
        entry = make_ledger_entry(
            decision_id="d1", stage="seed_audit", decision="x",
            confidence=-0.5,
        )
        assert entry["confidence"] == 0.0

    def test_invalid_stage_rejected(self):
        entry = make_ledger_entry(
            decision_id="d1", stage="bogus", decision="x",
        )
        assert validate_ledger_entry(entry) != []


class TestDefaultRe80State:
    def test_topic_only_defaults(self):
        s = default_re80_state()
        assert s["entry_mode"] == "topic_only"
        assert s["run_mode"] == "lite_chain"
        assert s["network_policy"] == "online"
        assert s["reasoning_policy"] == "chain_only"
        assert s["seed_cards"] == []
        assert s["candidate_seeds"] == []
        assert s["search_budget"]["max_queries"] == 20

    def test_invalid_entry_mode_falls_back(self):
        s = default_re80_state(entry_mode="bogus")
        assert s["entry_mode"] == "topic_only"


# ---------------------------------------------------------------------------
# Classifier + decision helpers (seed_resolver.py)
# ---------------------------------------------------------------------------

class TestClassifyInput:
    def test_doi(self):
        form, ident = _classify_input({"doi": "10.1000/test"})
        assert form == "doi"
        assert ident == "10.1000/test"

    def test_arxiv(self):
        form, ident = _classify_input({"arxiv_id": "2401.00001"})
        assert form == "arxiv"
        assert ident == "2401.00001"

    def test_title_only(self):
        form, ident = _classify_input({"title": "Some Paper"})
        assert form == "title"
        assert ident is None

    def test_url(self):
        form, ident = _classify_input({"url": "https://example.com/paper"})
        assert form == "url"

    def test_empty(self):
        form, ident = _classify_input({})
        assert form == "citation"
        assert ident is None


# ---------------------------------------------------------------------------
# Re8.0 P0-1: CandidateSeed input contract normalisation
# (raw_input nested fields → top-level flatten)
# ---------------------------------------------------------------------------

class TestSeedPayloadNormalization:
    """Re8.0 P0-1: ``_normalize_seed_payload`` + ``_classify_input`` must
    accept both flat top-level fields and nested ``raw_input`` dict, with
    top-level winning on conflicts. Covers all 4 spec scenarios:

    1. nested raw_input only (no top-level doi) → extract doi from raw_input
    2. top-level only (no raw_input) → existing behaviour unchanged
    3. both present → top-level wins (or they agree)
    4. neither → fall back to "citation" or "title"
    """

    def test_normalize_extracts_doi_from_raw_input(self):
        """Scenario 1: nested raw_input only → doi flattened up."""
        payload = {
            "seed_id": "S1",
            "raw_input": {"doi": "10.18653/v1/N19-1423", "title": "BERT"},
        }
        normalized = _normalize_seed_payload(payload)
        assert normalized["doi"] == "10.18653/v1/N19-1423"
        assert normalized["title"] == "BERT"
        # raw_input preserved verbatim on the normalized payload
        assert normalized["raw_input"] == {
            "doi": "10.18653/v1/N19-1423", "title": "BERT",
        }
        # Original payload not mutated
        assert "doi" not in payload

    def test_normalize_top_level_wins_over_raw_input(self):
        """Scenario 3: both present → top-level value wins, raw_input ignored."""
        payload = {
            "doi": "10.1000/top-level",
            "raw_input": {"doi": "10.1000/raw-only"},
        }
        normalized = _normalize_seed_payload(payload)
        assert normalized["doi"] == "10.1000/top-level"

    def test_normalize_no_raw_input_returns_copy(self):
        """Scenario 2: no raw_input → payload returned as shallow copy."""
        payload = {"doi": "10.1/x", "title": "T"}
        normalized = _normalize_seed_payload(payload)
        assert normalized == payload
        assert normalized is not payload  # not aliased

    def test_normalize_empty_raw_input_no_op(self):
        """raw_input={} → no fields to flatten."""
        payload = {"doi": "10.1/x", "raw_input": {}}
        normalized = _normalize_seed_payload(payload)
        assert normalized["doi"] == "10.1/x"

    def test_normalize_non_dict_payload_returns_empty(self):
        """Defensive: non-dict payload → empty dict (no crash)."""
        assert _normalize_seed_payload(None) == {}
        assert _normalize_seed_payload("not a dict") == {}

    def test_normalize_does_not_overwrite_empty_list_with_raw(self):
        """An empty list at top-level is treated as 'unset' and refilled
        from raw_input — matches the 'top-level wins only if truthy'
        contract for authors lists."""
        payload = {
            "authors": [],
            "raw_input": {"authors": ["Devlin", "Chang"]},
        }
        normalized = _normalize_seed_payload(payload)
        assert normalized["authors"] == ["Devlin", "Chang"]

    def test_classify_nested_doi_via_raw_input(self):
        """Scenario 1 end-to-end: raw_input has doi, top-level does not →
        _classify_input classifies as 'doi' with the nested identifier."""
        form, ident = _classify_input({
            "seed_id": "S1",
            "raw_input": {"doi": "10.18653/v1/N19-1423", "title": "BERT"},
        })
        assert form == "doi"
        assert ident == "10.18653/v1/N19-1423"

    def test_classify_nested_arxiv_url_via_raw_input(self):
        """Nested arxiv URL → still classified as arxiv (P1-1 extraction
        works post-normalisation)."""
        form, ident = _classify_input({
            "raw_input": {"url": "https://arxiv.org/abs/1911.02116"},
        })
        assert form == "arxiv"
        assert ident == "1911.02116"

    def test_classify_top_level_only_unchanged(self):
        """Scenario 2: flat top-level fields (no raw_input) → unchanged."""
        form, ident = _classify_input({"doi": "10.1000/test"})
        assert form == "doi"
        assert ident == "10.1000/test"

        form, ident = _classify_input({"title": "Just a Title"})
        assert form == "title"
        assert ident is None

    def test_classify_both_present_top_level_wins(self):
        """Scenario 3: both carry doi but disagree → top-level identifier used."""
        form, ident = _classify_input({
            "doi": "10.1000/top",
            "raw_input": {"doi": "10.1000/raw"},
        })
        assert form == "doi"
        assert ident == "10.1000/top"

    def test_classify_neither_top_nor_raw_falls_to_title_or_citation(self):
        """Scenario 4: no identifier anywhere → fall back to title (if
        present in raw_input) or citation (when nothing usable at all)."""
        # Title only in raw_input
        form, ident = _classify_input({"raw_input": {"title": "Some Title"}})
        assert form == "title"
        assert ident is None

        # Nothing useful at all
        form, ident = _classify_input({
            "seed_id": "S1",
            "raw_input": {"role": "classic_anchor"},
        })
        assert form == "citation"
        assert ident is None


class TestSeedResolverNestedRawInputIntegration:
    """Re8.0 P0-1 integration: ``seed_resolver_node`` receives a seed whose
    identifier lives ONLY in ``raw_input``. The Resolver must normalise it
    up, fetch metadata, and verify the seed — NOT silently mark it
    ambiguous (which was the pre-fix bug).
    """

    def test_nested_doi_seed_gets_verified(self):
        """Mock Crossref returns matching metadata for the nested DOI →
        card becomes verified + promoted to evidence."""
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {
                    "seed_id": "S1",
                    "raw_input": {
                        "doi": "10.18653/v1/N19-1423",
                        "title": "BERT",
                        "role": "classic_anchor",
                    },
                    "role": "classic_anchor",
                },
            ],
        }
        fetched = {
            "title": "BERT",
            "authors": ["Devlin"],
            "year": 2019,
            "doi": "10.18653/v1/N19-1423",
            "canonical_url": "https://doi.org/10.18653/v1/N19-1423",
        }
        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_crossref",
            new_callable=AsyncMock,
            return_value=fetched,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 1
        # Critical: must NOT be ambiguous — DOI was in raw_input, normalised up
        assert cards[0]["existence_status"] == "verified"
        assert cards[0]["doi"] == "10.18653/v1/N19-1423"
        assert cards[0]["input_form"] == "doi"
        # Promoted to evidence
        assert len(result["verified_papers"]) == 1
        # raw_input preserved on the card for audit: the original payload
        # is stored verbatim, so the user-supplied nested raw_input dict
        # is still accessible at card["raw_input"]["raw_input"].
        assert cards[0]["raw_input"]["raw_input"]["doi"] == "10.18653/v1/N19-1423"

    def test_nested_arxiv_url_seed_gets_verified(self):
        """Nested arxiv URL → normalised up → classified as arxiv → verified."""
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {
                    "seed_id": "S1",
                    "raw_input": {
                        "url": "https://arxiv.org/abs/1911.02116",
                        "title": "XLM-R",
                        "role": "current_sota_candidate",
                    },
                    "role": "current_sota_candidate",
                },
            ],
        }
        fetched = {
            "title": "XLM-R",
            "authors": ["Conneau"],
            "year": 2020,
            "arxiv_id": "1911.02116",
            "canonical_url": "https://arxiv.org/abs/1911.02116",
        }
        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_arxiv",
            new_callable=AsyncMock,
            return_value=fetched,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 1
        assert cards[0]["existence_status"] == "verified"
        assert cards[0]["input_form"] == "arxiv"
        assert len(result["verified_papers"]) == 1


class TestAuthorLastname:
    """Re8.0 P0-B: ``_author_lastname`` normalises both ``"Devlin, J."``
    (surname-first) and ``"Jacob Devlin"`` (given-first) forms to the
    same lower-cased surname. Without this, the existence check rejects
    papers whose authors are actually identical (Crossref returns
    ``"given family"`` while user seeds often carry ``"Family, G."``).
    """

    def test_author_lastname_surname_first_format(self):
        """``"Devlin, J."`` -> ``"devlin"`` (user seed surname-first style)."""
        assert _author_lastname("Devlin, J.") == "devlin"

    def test_author_lastname_given_first_format(self):
        """``"Jacob Devlin"`` -> ``"devlin"`` (Crossref given-first style)."""
        assert _author_lastname("Jacob Devlin") == "devlin"

    def test_author_lastname_empty(self):
        """Empty string -> empty string (no crash)."""
        assert _author_lastname("") == ""

    def test_author_lastname_none(self):
        """None -> empty string (defensive null handling)."""
        assert _author_lastname(None) == ""

    def test_author_lastname_single_name(self):
        """``"Devlin"`` -> ``"devlin"`` (single token, no comma)."""
        assert _author_lastname("Devlin") == "devlin"

    def test_author_lastname_multiple_commas(self):
        """``"Smith, John, Jr."`` -> ``"smith"`` (first comma-split segment wins)."""
        assert _author_lastname("Smith, John, Jr.") == "smith"


class TestTitlesAgree:
    def test_exact_match(self):
        assert _titles_agree("Attention Is All You Need", "Attention Is All You Need")

    def test_case_insensitive(self):
        assert _titles_agree("attention is all you need", "Attention Is All You Need")

    def test_punctuation_tolerant(self):
        assert _titles_agree("Attention: Is All You Need!", "Attention Is All You Need")

    def test_substring(self):
        assert _titles_agree("Attention", "Attention Is All You Need")

    def test_mismatch(self):
        assert not _titles_agree("Transformer", "GAN")


class TestDecideExistence:
    def test_fetched_none_with_title(self):
        status, hint = _decide_existence({"title": "X"}, None)
        assert status == "ambiguous"
        assert hint is not None

    def test_fetched_none_no_title(self):
        status, hint = _decide_existence({}, None)
        assert status == "not_found"

    def test_title_match_verified(self):
        candidate = {"title": "Attention Is All You Need"}
        fetched = {"title": "Attention Is All You Need", "authors": ["Vaswani"]}
        status, hint = _decide_existence(candidate, fetched)
        assert status == "verified"
        assert hint is None

    def test_title_mismatch_ambiguous(self):
        candidate = {"title": "Transformer X"}
        fetched = {"title": "GAN Paper", "authors": ["Goodfellow"]}
        status, hint = _decide_existence(candidate, fetched)
        assert status == "ambiguous"
        assert "mismatch" in (hint or "")

    def test_author_mismatch_ambiguous(self):
        candidate = {"title": "Same Title", "authors": ["Alice"]}
        fetched = {"title": "Same Title", "authors": ["Bob"]}
        status, hint = _decide_existence(candidate, fetched)
        assert status == "ambiguous"
        assert "author" in (hint or "").lower()


# ---------------------------------------------------------------------------
# seed_resolver_node (LangGraph node)
# ---------------------------------------------------------------------------

class TestSeedResolverNodeNoop:
    """No-op conditions: topic_only or empty candidate_seeds."""

    def test_topic_only_returns_trace_only(self):
        state = {
            "entry_mode": "topic_only",
            "candidate_seeds": [{"seed_id": "s1", "title": "X"}],
        }
        result = seed_resolver_node(state)
        assert "seed_cards" not in result
        assert "verified_papers" not in result
        assert "trace_events" in result
        assert len(result["trace_events"]) == 1
        assert result["trace_events"][0].get("output_summary", {}).get("skipped") is True

    def test_empty_candidate_seeds_skipped(self):
        state = {
            "entry_mode": "seeded_research",
            "candidate_seeds": [],
        }
        result = seed_resolver_node(state)
        assert "seed_cards" not in result
        assert result["trace_events"][0]["output_summary"]["skipped"] is True


class TestSeedResolverOffline:
    """Offline mode: all seeds become ambiguous (no network)."""

    def test_offline_makes_all_ambiguous(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "offline",
            "candidate_seeds": [
                {"seed_id": "s1", "doi": "10.1000/fake", "title": "Fake Paper"},
                {"seed_id": "s2", "title": "Title Only"},
            ],
        }
        result = seed_resolver_node(state)
        cards = result["seed_cards"]
        assert len(cards) == 2
        assert all(c["existence_status"] == "ambiguous" for c in cards)
        # No papers promoted to evidence in offline mode
        assert result["verified_papers"] == []
        assert result["seed_papers"] == []
        # Ledger records the audit
        assert len(result["reasoning_ledger"]) == 2
        assert all(e["stage"] == "seed_audit" for e in result["reasoning_ledger"])


class TestSeedResolverFabricatedDoi:
    """Core safety: fabricated DOI (Crossref returns None) must NOT enter
    verified_papers. This is the Re8.0 §3 loophole fix."""

    def test_fabricated_doi_not_promoted(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {"seed_id": "s1", "doi": "10.9999/does-not-exist",
                 "title": "Hallucinated Paper"},
            ],
        }
        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_crossref",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 1
        # Fabricated DOI → ambiguous (has title) or not_found
        assert cards[0]["existence_status"] in ("ambiguous", "not_found")
        # MUST NOT be in verified_papers
        assert result["verified_papers"] == []
        assert result["seed_papers"] == []


class TestSeedResolverVerifiedPaper:
    """A real paper (Crossref returns matching metadata) gets verified and
    promoted to verified_papers + seed_papers."""

    def test_real_paper_promoted(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {"seed_id": "s1", "doi": "10.1000/real",
                 "title": "Real Paper Title", "authors": ["Alice"],
                 "role": "classic_anchor"},
            ],
        }
        fetched = {
            "title": "Real Paper Title",
            "authors": ["Alice", "Bob"],
            "year": 2023,
            "doi": "10.1000/real",
            "canonical_url": "https://doi.org/10.1000/real",
            "abstract": "An abstract.",
        }
        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_crossref",
            new_callable=AsyncMock,
            return_value=fetched,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 1
        assert cards[0]["existence_status"] == "verified"
        assert cards[0]["resolved_title"] == "Real Paper Title"
        assert cards[0]["doi"] == "10.1000/real"
        # Promoted to evidence
        assert len(result["verified_papers"]) == 1
        assert result["verified_papers"][0]["title"] == "Real Paper Title"
        assert result["verified_papers"][0]["source"] == "user_seed_verified"
        assert result["verified_papers"][0]["verdict"] == "accept"
        assert len(result["seed_papers"]) == 1
        # Ledger entry marked verified
        ledger = result["reasoning_ledger"]
        assert len(ledger) == 1
        assert ledger[0]["status"] == "verified"
        assert ledger[0]["confidence"] == 0.9


class TestSeedResolverPdfInput:
    """Local PDF input: no network needed, marked verified-local."""

    def test_pdf_input_verified_local(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {"seed_id": "s1", "pdf_path": "/tmp/paper.pdf",
                 "title": "Local PDF Paper"},
            ],
        }
        result = seed_resolver_node(state)
        cards = result["seed_cards"]
        assert len(cards) == 1
        assert cards[0]["input_form"] == "pdf"
        assert cards[0]["existence_status"] == "verified"
        # PDF cards have repair_hint about pending fulltext parse
        assert "fulltext" in (cards[0].get("repair_hint") or "").lower()


class TestSeedResolverTitleMismatch:
    """DOI points to a different paper (title mismatch) → ambiguous."""

    def test_doi_points_to_different_paper(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {"seed_id": "s1", "doi": "10.1000/real-doi",
                 "title": "User Claimed Title"},
            ],
        }
        fetched = {
            "title": "Completely Different Paper",
            "authors": ["Someone Else"],
            "doi": "10.1000/real-doi",
        }
        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_crossref",
            new_callable=AsyncMock,
            return_value=fetched,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert cards[0]["existence_status"] == "ambiguous"
        assert "mismatch" in (cards[0].get("repair_hint") or "").lower()
        assert result["verified_papers"] == []


class TestSeedResolverArxiv:
    """arXiv ID with matching metadata → verified."""

    def test_arxiv_paper_promoted(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {"seed_id": "s1", "arxiv_id": "2401.00001",
                 "title": "arXiv Paper"},
            ],
        }
        fetched = {
            "title": "arXiv Paper",
            "authors": ["Author A"],
            "year": 2024,
            "arxiv_id": "2401.00001",
            "canonical_url": "https://arxiv.org/abs/2401.00001",
        }
        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_arxiv",
            new_callable=AsyncMock,
            return_value=fetched,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert cards[0]["existence_status"] == "verified"
        assert len(result["verified_papers"]) == 1


class TestSeedResolverMultipleSeeds:
    """Mix of verified + ambiguous + not_found in one batch."""

    def test_mixed_batch(self):
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {"seed_id": "real", "doi": "10.1/real", "title": "Real"},
                {"seed_id": "fake", "doi": "10.1/fake", "title": "Fake"},
                {"seed_id": "titleonly", "title": "Just A Title"},
                {"seed_id": "titleonly_no_match", "title": "Obscure Paper That Does Not Exist"},
            ],
        }
        real_fetched = {
            "title": "Real", "authors": ["A"], "doi": "10.1/real",
            "canonical_url": "https://doi.org/10.1/real",
        }
        title_fetched = {
            "title": "Just A Title", "authors": ["B"], "doi": "10.2/title",
            "canonical_url": "https://doi.org/10.2/title",
        }

        async def mock_crossref(doi):
            if doi == "10.1/real":
                return real_fetched
            return None

        async def mock_fetch_by_title(title, authors=None, year=None):
            if title == "Just A Title":
                return title_fetched
            return None

        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_crossref",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_by_title",
            new=mock_fetch_by_title,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 4
        statuses = {c["seed_id"]: c["existence_status"] for c in cards}
        assert statuses["real"] == "verified"
        assert statuses["fake"] in ("ambiguous", "not_found")
        assert statuses["titleonly"] == "verified"
        assert statuses["titleonly_no_match"] == "ambiguous"
        # real + titleonly promoted
        assert len(result["verified_papers"]) == 2
        verified_ids = {p["seed_id"] for p in result["verified_papers"]}
        assert verified_ids == {"real", "titleonly"}
        # 4 ledger entries
        assert len(result["reasoning_ledger"]) == 4


# ---------------------------------------------------------------------------
# Re8.0 second batch: Seed Repair title-search capability
# ---------------------------------------------------------------------------

class TestSeedResolverTitleSearch:
    """Step 3: _fetch_by_title + _resolve_one_seed title branch.

    Previously a title-only seed (no DOI/arxiv) short-circuited to
    ``ambiguous`` without any network attempt. Now ``_resolve_one_seed``
    calls ``_fetch_by_title`` (Crossref + Semantic Scholar in parallel)
    and promotes to ``verified`` when a match is found.
    """

    def test_normalize_title_hit_crossref(self):
        """_normalize_title_hit maps crossref fields to _decide_existence schema."""
        hit = {
            "title": "Test Paper",
            "authors": ["Alice", "Bob"],
            "year": 2024,
            "doi": "10.1/test",
            "url": "https://doi.org/10.1/test",
            "abstract": "An abstract",
        }
        norm = _normalize_title_hit(hit, "crossref")
        assert norm["title"] == "Test Paper"
        assert norm["authors"] == ["Alice", "Bob"]
        assert norm["year"] == 2024
        assert norm["doi"] == "10.1/test"
        assert norm["canonical_url"] == "https://doi.org/10.1/test"
        assert norm["abstract"] == "An abstract"

    def test_normalize_title_hit_semantic_scholar(self):
        """_normalize_title_hit maps s2 fields (uses url fallback)."""
        hit = {
            "title": "S2 Paper",
            "authors": ["Carol"],
            "year": 2023,
            "doi": "10.2/s2",
            "url": "https://www.semanticscholar.org/paper/123",
            "abstract": None,
        }
        norm = _normalize_title_hit(hit, "semantic_scholar")
        assert norm["title"] == "S2 Paper"
        assert norm["canonical_url"] == "https://www.semanticscholar.org/paper/123"
        assert norm["abstract"] == ""

    @pytest.mark.asyncio
    async def test_fetch_by_title_returns_match(self):
        """_fetch_by_title picks the candidate with DOI when titles agree."""
        crossref_hits = [
            {"title": "Just A Title", "authors": ["B"], "doi": "10.2/title",
             "url": "https://doi.org/10.2/title", "year": 2024, "abstract": ""},
        ]
        s2_hits = [
            {"title": "Just A Title", "authors": ["B"], "doi": None,
             "url": "https://s2/paper/1", "year": 2024, "abstract": ""},
        ]

        async def mock_crossref(queries, top_k=8, **kwargs):
            return crossref_hits

        async def mock_s2(queries, top_k=8, **kwargs):
            return s2_hits

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            result = await _fetch_by_title("Just A Title", authors=["B"])

        assert result is not None
        assert result["doi"] == "10.2/title"
        assert result["title"] == "Just A Title"

    @pytest.mark.asyncio
    async def test_fetch_by_title_no_match_returns_none(self):
        """_fetch_by_title returns None when no title agrees."""
        crossref_hits = [
            {"title": "Completely Different", "authors": ["X"], "doi": "10.1/x"},
        ]
        s2_hits = []

        async def mock_crossref(queries, top_k=8, **kwargs):
            return crossref_hits

        async def mock_s2(queries, top_k=8, **kwargs):
            return s2_hits

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            result = await _fetch_by_title("Just A Title")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_by_title_network_failure_returns_none(self):
        """_fetch_by_title returns None (not raises) when both sources fail."""
        async def mock_crossref(queries, top_k=8, **kwargs):
            raise ConnectionError("crossref down")

        async def mock_s2(queries, top_k=8, **kwargs):
            raise ConnectionError("s2 down")

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            result = await _fetch_by_title("Just A Title")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_by_title_prefers_doi_candidate(self):
        """When two sources return matches, the one with DOI wins."""
        crossref_hits = [
            {"title": "Paper X", "authors": ["A"], "doi": "10.1/x",
             "url": "https://doi.org/10.1/x", "year": 2024, "abstract": ""},
        ]
        s2_hits = [
            {"title": "Paper X", "authors": ["A"], "doi": None,
             "url": "https://s2/paper/x", "year": 2024, "abstract": ""},
        ]

        async def mock_crossref(queries, top_k=8, **kwargs):
            return crossref_hits

        async def mock_s2(queries, top_k=8, **kwargs):
            return s2_hits

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            result = await _fetch_by_title("Paper X")

        assert result is not None
        assert result["doi"] == "10.1/x"

    def test_resolve_title_seed_verified(self):
        """_resolve_one_seed calls _fetch_by_title and promotes to verified."""
        from apps.api.app.services.agents.graph.nodes.seed_resolver import _resolve_one_seed

        title_fetched = {
            "title": "Just A Title", "authors": ["B"], "doi": "10.2/title",
            "canonical_url": "https://doi.org/10.2/title", "year": 2024,
            "abstract": "",
        }

        async def mock_fetch_by_title(title, authors=None, year=None):
            return title_fetched

        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_by_title",
            new=mock_fetch_by_title,
        ):
            import asyncio
            card = asyncio.run(_resolve_one_seed(
                "s1",
                {"seed_id": "s1", "title": "Just A Title"},
                offline=False,
            ))

        assert card["existence_status"] == "verified"
        assert card["resolved_title"] == "Just A Title"
        assert card["doi"] == "10.2/title"
        assert card["canonical_url"] == "https://doi.org/10.2/title"

    def test_resolve_title_seed_ambiguous_on_no_match(self):
        """_resolve_one_seed stays ambiguous when _fetch_by_title returns None."""
        from apps.api.app.services.agents.graph.nodes.seed_resolver import _resolve_one_seed

        async def mock_fetch_by_title(title, authors=None, year=None):
            return None

        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_by_title",
            new=mock_fetch_by_title,
        ):
            import asyncio
            card = asyncio.run(_resolve_one_seed(
                "s2",
                {"seed_id": "s2", "title": "Obscure Nonexistent Paper"},
                offline=False,
            ))

        assert card["existence_status"] == "ambiguous"
        assert "title search found no authoritative match" in (card.get("repair_hint") or "")


# ---------------------------------------------------------------------------
# P1-1 regression: arXiv URL extraction (unanchored pattern)
# ---------------------------------------------------------------------------

class TestArxivUrlExtraction:
    """P1-1 fix: _ARXIV_URL_RE must extract arxiv ID from full URLs."""

    def test_arxiv_url_classified_as_arxiv(self):
        form, ident = _classify_input({"url": "https://arxiv.org/abs/2401.00001"})
        assert form == "arxiv"
        assert ident == "2401.00001"

    def test_arxiv_url_with_version(self):
        form, ident = _classify_input({"url": "https://arxiv.org/abs/2401.00001v2"})
        assert form == "arxiv"
        assert ident == "2401.00001v2"

    def test_old_style_arxiv_url(self):
        form, ident = _classify_input({"url": "https://arxiv.org/abs/cs.LG/0703001"})
        assert form == "arxiv"
        assert ident == "cs.LG/0703001"

    def test_non_arxiv_url_still_url(self):
        form, ident = _classify_input({"url": "https://example.com/paper"})
        assert form == "url"


# ---------------------------------------------------------------------------
# P1-5: seed_resolver → verify integration (existing_verified merge)
# ---------------------------------------------------------------------------

class TestSeedResolverVerifyIntegration:
    """P1-5: verify that verify_node's first-round existing_verified merge
    correctly preserves seed_resolver-promoted papers."""

    @pytest.fixture(autouse=True)
    def _enable_contract_path(self, monkeypatch):
        """Force the unified-router contract path so the mocked
        ``call_with_contract_list`` is actually invoked. Without this,
        ``_call_verifier`` defaults to the legacy ``llm_router.call_json``
        path (USE_CONTRACT_PATH=0) and the patch never fires — the mock
        verdicts would never reach ``keep``."""
        monkeypatch.setenv("USE_CONTRACT_PATH", "1")

    def _make_contract_result(self, verdicts: list):
        from apps.api.app.services.router.unified_router import ContractResult
        return ContractResult(
            success=True,
            content=verdicts,
            contract_id="verification-batch/v1",
            provider_chain=["mock", "mock-model"],
            heuristic_fallback=False,
            error=None,
        )

    def _make_verify_state(self, existing_verified, n_candidates=2):
        return {
            "topic": "Test topic",
            "topic_atoms": {"method": ["test"], "object": ["x"], "task": ["y"],
                           "dataset_terms": ["Z"]},
            "paper_candidates": [
                {
                    "title": f"Candidate {i}",
                    "candidate_id": f"cand_{i}",
                    "abstract": f"Abstract {i}",
                    "source": "arxiv",
                    "url": f"https://arxiv.org/abs/2601.{i:04d}",
                }
                for i in range(n_candidates)
            ],
            "verified_papers": existing_verified,
            "verify_scope": "search",
            "citation_expansion_done": False,
            "trace_events": [],
            "errors": [],
        }

    def test_seed_paper_preserved_through_verify(self):
        """Seed_resolver promoted a paper; verify_node must not overwrite it."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        seed_paper = {
            "title": "Seed Paper From Resolver",
            "doi": "10.1000/seed",
            "source": "user_seed_verified",
            "verdict": "accept",
            "seed_id": "seed-1",
        }
        state = self._make_verify_state(existing_verified=[seed_paper], n_candidates=2)

        # Mock LLM returns 1 accept + 1 reject
        verdicts = [
            {"candidate_id": "cand_0", "verdict": "accept",
             "relation_to_topic": "baseline", "reason": "ok"},
            {"candidate_id": "cand_1", "verdict": "reject",
             "relation_to_topic": "none", "reason": "unrelated"},
        ]
        with patch(
            "apps.api.app.services.router.call_with_contract_list",
            return_value=self._make_contract_result(verdicts),
        ):
            result = verify_node(state)

        verified = result.get("verified_papers", [])
        # Should have seed_paper + 1 new accept = 2
        assert len(verified) == 2
        titles = [p.get("title") for p in verified]
        assert "Seed Paper From Resolver" in titles
        assert "Candidate 0" in titles

    def test_dedup_when_verify_accepts_same_title_as_seed(self):
        """If verify's accept candidate has the same title as a seed paper,
        dedup should prevent duplication (P1-4 fix)."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        seed_paper = {
            "title": "Duplicate Title",
            "doi": "10.1000/seed",
            "source": "user_seed_verified",
            "verdict": "accept",
        }
        state = self._make_verify_state(existing_verified=[seed_paper], n_candidates=1)
        # Override candidate to have same title as seed
        state["paper_candidates"][0]["title"] = "Duplicate Title"

        verdicts = [
            {"candidate_id": "cand_0", "verdict": "accept",
             "relation_to_topic": "baseline", "reason": "ok"},
        ]
        with patch(
            "apps.api.app.services.router.call_with_contract_list",
            return_value=self._make_contract_result(verdicts),
        ):
            result = verify_node(state)

        verified = result.get("verified_papers", [])
        # Should dedup by title → only 1 paper, not 2
        titles = [p.get("title") for p in verified]
        assert titles.count("Duplicate Title") == 1

    def test_dedup_by_doi_when_title_empty(self):
        """P1-4: dedup by DOI when title is empty."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        seed_paper = {
            "title": "",
            "doi": "10.1000/seed-doi",
            "source": "user_seed_verified",
            "verdict": "accept",
        }
        state = self._make_verify_state(existing_verified=[seed_paper], n_candidates=1)
        state["paper_candidates"][0]["title"] = ""
        state["paper_candidates"][0]["doi"] = "10.1000/seed-doi"

        verdicts = [
            {"candidate_id": "cand_0", "verdict": "accept",
             "relation_to_topic": "baseline", "reason": "ok"},
        ]
        with patch(
            "apps.api.app.services.router.call_with_contract_list",
            return_value=self._make_contract_result(verdicts),
        ):
            result = verify_node(state)

        verified = result.get("verified_papers", [])
        # Same DOI → dedup → only 1
        dois = [p.get("doi") for p in verified if p.get("doi")]
        assert dois.count("10.1000/seed-doi") == 1

    def test_topic_only_no_existing_verified_unchanged(self):
        """topic_only path: no existing_verified → verify behaves as before."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_verify_state(existing_verified=[], n_candidates=2)
        verdicts = [
            {"candidate_id": "cand_0", "verdict": "accept",
             "relation_to_topic": "baseline", "reason": "ok"},
            {"candidate_id": "cand_1", "verdict": "reject",
             "relation_to_topic": "none", "reason": "unrelated"},
        ]
        with patch(
            "apps.api.app.services.router.call_with_contract_list",
            return_value=self._make_contract_result(verdicts),
        ):
            result = verify_node(state)

        verified = result.get("verified_papers", [])
        # No existing → just 1 new accept
        assert len(verified) == 1
        assert verified[0]["title"] == "Candidate 0"


# ---------------------------------------------------------------------------
# P1-7: list_user_papers triple-count fix
# ---------------------------------------------------------------------------

class TestListUserPapersDedup:
    """P1-7: _paper_dedup_keys + _collect_user_papers must not triple-count
    a paper that exists in _USER_PAPERS, candidate_seeds, AND seed_cards."""

    def test_dedup_keys_collects_all_identifiers(self):
        from apps.api.app.api.v1.research import _paper_dedup_keys
        p = {"seed_id": "s1", "doi": "10.1/x", "title": "T"}
        keys = _paper_dedup_keys(p)
        assert "s1" in keys
        assert "10.1/x" in keys
        assert "t" in keys

    def test_dedup_keys_handles_missing_fields(self):
        from apps.api.app.api.v1.research import _paper_dedup_keys
        assert _paper_dedup_keys({}) == set()
        assert _paper_dedup_keys({"title": "My Paper"}) == {"my paper"}

    def test_dedup_keys_overlapping_doi(self):
        """Two papers with same DOI but different seed_ids must dedup."""
        from apps.api.app.api.v1.research import _paper_dedup_keys
        a = {"doi": "10.1/x", "title": "A"}
        b = {"seed_id": "s1", "doi": "10.1/x", "title": "B"}
        # Intersection on doi → duplicate
        assert _paper_dedup_keys(a) & _paper_dedup_keys(b) == {"10.1/x"}

    def test_collect_no_triple_count(self, monkeypatch):
        """Same paper in _USER_PAPERS + candidate_seeds + seed_cards → 1 entry."""
        import json
        from pathlib import Path
        from apps.api.app.api.v1 import research as R

        case_id = "test-p17"
        # Simulate _USER_PAPERS entry (pre-run, no seed_id)
        paper = {"title": "Triple Threat", "doi": "10.1000/triple",
                 "url": "https://example.com/p"}
        monkeypatch.setattr(R, "_USER_PAPERS", {case_id: [paper]})

        # Write state.json to a project-local temp dir (avoids Windows
        # pytest tmp_path permission issues)
        state = {
            "candidate_seeds": [{
                "seed_id": "user-seed-0",
                "title": "Triple Threat",
                "doi": "10.1000/triple",
                "raw_input": paper,
            }],
            "seed_cards": [{
                "seed_id": "user-seed-0",
                "doi": "10.1000/triple",
                "resolved_title": "Triple Threat",
                "existence_status": "verified",
                "raw_input": paper,
            }],
        }
        fake_dir = Path("g:/PaperAgent/.pytest_tmp/test_p17")
        fake_dir.mkdir(parents=True, exist_ok=True)
        (fake_dir / "state.json").write_text(
            json.dumps(state), encoding="utf-8")

        monkeypatch.setattr(R, "_case_dir", lambda cid: fake_dir)

        result = R._collect_user_papers(case_id)
        # Must NOT be 3 — should be 1 (deduped by doi)
        assert result["n"] == 1, f"expected 1, got {result['n']}: {result['papers']}"

        # Cleanup
        (fake_dir / "state.json").unlink(missing_ok=True)
        fake_dir.rmdir()


# ---------------------------------------------------------------------------
# Re8.1 WP2 Task 9 — Seed Repair capability tests
# ---------------------------------------------------------------------------

class TestTitleSimilarity:
    """Capability 1: ``_title_similarity`` returns a similarity score in
    [0.0, 1.0] using Jaccard (0.6) + Levenshtein ratio (0.4)."""

    def test_title_similarity_exact_match(self):
        """Identical titles (post-normalisation) → 1.0."""
        t = "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale"
        assert _title_similarity(t, t) == 1.0

    def test_title_similarity_typo(self):
        """Single-character typo → still > 0.85 (covers typo_light cases)."""
        a = "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale"
        b = "An Image is Worth 16x16 Words: Transformers for Image Recogntion at Scale"
        sim = _title_similarity(a, b)
        assert sim > 0.85, f"expected >0.85 for typo, got {sim}"

    def test_title_similarity_different(self):
        """Completely unrelated titles → < 0.3."""
        a = "Attention is All You Need"
        b = "Quantum-Entangled Transformer Networks for Time-Travel-Based Image Generation"
        sim = _title_similarity(a, b)
        assert sim < 0.3, f"expected <0.3 for unrelated, got {sim}"

    def test_title_similarity_normalization(self):
        """Case / punctuation / whitespace differences must not lower
        the score below 1.0 when the normalised form is identical."""
        a = "BERT: Pre-training of Deep Bidirectional Transformers!"
        b = "bert  pre training of deep bidirectional transformers"
        sim = _title_similarity(a, b)
        assert sim == 1.0, f"expected 1.0 after normalisation, got {sim}"

    def test_title_similarity_empty(self):
        """Either side empty → 0.0 (defensive)."""
        assert _title_similarity("", "Anything") == 0.0
        assert _title_similarity("Anything", "") == 0.0
        assert _title_similarity("", "") == 0.0


class TestYearPenalty:
    """Capability 2: ``_year_penalty`` returns a multiplier in [0.3, 1.0]."""

    def test_year_penalty_no_input_year(self):
        """input_year=None → 1.0 (cannot compare; no penalty)."""
        assert _year_penalty(None, 2020) == 1.0

    def test_year_penalty_consistent(self):
        """|delta| <= 2 → 1.0 (within tolerance)."""
        assert _year_penalty(2020, 2020) == 1.0
        assert _year_penalty(2020, 2022) == 1.0
        assert _year_penalty(2020, 2018) == 1.0

    def test_year_penalty_conflict(self):
        """|delta| > 2 → < 1.0 (penalty applied)."""
        assert _year_penalty(2020, 2025) < 1.0
        # Linear decay: delta=5 → 1.0 - (5-2)*0.1 = 0.7
        assert _year_penalty(2020, 2025) == 0.7

    def test_year_penalty_no_candidate_year(self):
        """candidate_year=None → 0.7 (moderate: unverifiable)."""
        assert _year_penalty(2020, None) == 0.7

    def test_year_penalty_floor(self):
        """Very large delta never goes below 0.3 (linear decay floor)."""
        # delta=20 → 1.0 - 18*0.1 = -0.8, clamped to 0.3
        assert _year_penalty(2000, 2020) == 0.3
        assert _year_penalty(1950, 2024) == 0.3


class TestComputeConfidence:
    """Capability 3: ``_compute_confidence`` returns (level, reasons)."""

    def test_confidence_high(self):
        """DOI + full author match + title sim ≥0.9 + year consistent → high."""
        candidate = {
            "title": "Attention is All You Need",
            "authors": ["Vaswani", "Shazeer", "Parmar"],
            "year": 2017,
            "doi": "10.5555/3295222.3295349",
        }
        input_meta = {
            "title": "Attention is All You Need",
            "authors": ["Vaswani"],
            "year": 2017,
        }
        level, reasons = _compute_confidence(candidate, input_meta)
        assert level == "high"
        assert "doi_match" in reasons
        assert "authors_full_match" in reasons
        assert any(r.startswith("title_similarity_") for r in reasons)
        assert "year_consistent" in reasons

    def test_confidence_medium(self):
        """Partial match (some signals missing) → medium."""
        candidate = {
            "title": "Attention is All You Need",
            "authors": ["Vaswani", "Shazeer"],
            "year": 2017,
            "doi": None,  # no DOI
        }
        input_meta = {
            "title": "Attention is All You Need",
            "authors": ["Vaswani"],
            "year": 2017,
        }
        level, reasons = _compute_confidence(candidate, input_meta)
        # 0.3 (authors_full_match) + 0.2 (title>=0.9) + 0.1 (year) = 0.6 → medium
        assert level == "medium"
        assert "authors_full_match" in reasons
        assert "doi_match" not in reasons

    def test_confidence_low(self):
        """No DOI + partial author match + medium title similarity → low."""
        candidate = {
            "title": "Masked Autoencoders Are Scalable Vision Learners",
            "authors": ["He"],
            "year": 2022,
            "doi": None,
        }
        input_meta = {
            "title": "Masked Autoencoders Are Good Vision Learners",
            "authors": ["Different"],
            "year": 2022,
        }
        level, reasons = _compute_confidence(candidate, input_meta)
        assert level == "low"
        # No DOI, no author match → very low score
        assert "doi_match" not in reasons
        assert "authors_full_match" not in reasons

    def test_confidence_reasons_recorded(self):
        """ranking_reasons is always non-empty when both titles provided."""
        candidate = {"title": "Some Paper", "authors": ["A"], "year": 2024, "doi": "10.1/x"}
        input_meta = {"title": "Some Paper", "authors": ["A"], "year": 2024}
        _, reasons = _compute_confidence(candidate, input_meta)
        assert isinstance(reasons, list)
        assert len(reasons) > 0
        # Each reason is a non-empty string
        assert all(isinstance(r, str) and r for r in reasons)

    def test_confidence_partial_authors_only(self):
        """Authors partial match (intersection non-empty) → +0.15."""
        candidate = {
            "title": "Paper Title",
            "authors": ["Alice", "Bob", "Carol"],
            "year": 2024,
            "doi": None,
        }
        input_meta = {
            "title": "Paper Title",
            "authors": ["Alice", "David"],  # David not in candidate
            "year": 2024,
        }
        _, reasons = _compute_confidence(candidate, input_meta)
        assert "authors_partial_match" in reasons
        assert "authors_full_match" not in reasons


class TestMergeWithConflictTagging:
    """Capability 4: ``_merge_with_conflict_tagging`` preserves dual-source
    evidence and tags conflicts. Never silently drops a candidate."""

    def test_merge_consistent(self):
        """Both sources return the same DOI → merged into one candidate,
        ``sources=["crossref", "semantic_scholar"]``, ``conflict=False``."""
        crossref = [{
            "title": "Attention is All You Need",
            "authors": ["Vaswani"],
            "year": 2017,
            "doi": "10.5555/3295222.3295349",
        }]
        s2 = [{
            "title": "Attention is All You Need",
            "authors": ["Vaswani"],
            "year": 2017,
            "doi": "10.5555/3295222.3295349",
        }]
        merged = _merge_with_conflict_tagging(crossref, s2)
        assert len(merged) == 1
        assert sorted(merged[0]["sources"]) == ["crossref", "semantic_scholar"]
        assert merged[0]["conflict"] is False

    def test_merge_conflict(self):
        """Same title, different DOIs (or no DOI) → BOTH candidates kept,
        each tagged ``conflict=True`` and ``conflict_type="title_match_doi_mismatch"``."""
        crossref = [{
            "title": "Generative Adversarial Networks",
            "authors": ["Goodfellow"],
            "year": 2014,
            "doi": None,  # no DOI to verify identity
        }]
        s2 = [{
            "title": "Generative Adversarial Networks",
            "authors": ["Goodfellow"],
            "year": 2014,
            "doi": None,
        }]
        merged = _merge_with_conflict_tagging(crossref, s2)
        # Both must be preserved (no silent drop)
        assert len(merged) == 2
        for c in merged:
            assert c["conflict"] is True
            assert c["conflict_type"] == "title_match_doi_mismatch"
        # Each source represented once
        sources = [c["sources"][0] for c in merged]
        assert "crossref" in sources
        assert "semantic_scholar" in sources

    def test_merge_single_source(self):
        """Only one source has a candidate → single-source tagging."""
        crossref = [{
            "title": "Only In Crossref",
            "authors": ["A"],
            "year": 2024,
            "doi": "10.1/only-cr",
        }]
        merged = _merge_with_conflict_tagging(crossref, [])
        assert len(merged) == 1
        assert merged[0]["sources"] == ["crossref"]
        assert merged[0]["conflict"] is False

        # Reverse: only s2 has candidates
        s2 = [{
            "title": "Only In S2",
            "authors": ["B"],
            "year": 2024,
            "doi": "10.1/only-s2",
        }]
        merged = _merge_with_conflict_tagging([], s2)
        assert len(merged) == 1
        assert merged[0]["sources"] == ["semantic_scholar"]
        assert merged[0]["conflict"] is False

    def test_merge_no_silent_drop(self):
        """Conflicting candidates (different DOIs, same title) must both
        be retained — never silently dropped."""
        crossref = [{
            "title": "Same Title Different Paper",
            "authors": ["AuthorA"],
            "year": 2024,
            "doi": "10.1/cr-version",
        }]
        s2 = [{
            "title": "Same Title Different Paper",
            "authors": ["AuthorB"],
            "year": 2024,
            "doi": "10.1/s2-version",
        }]
        merged = _merge_with_conflict_tagging(crossref, s2)
        # Different DOIs → both retained as separate candidates
        assert len(merged) == 2
        dois = {c.get("doi") for c in merged}
        assert dois == {"10.1/cr-version", "10.1/s2-version"}

    def test_merge_empty_inputs(self):
        """Both sources empty → empty list (no crash)."""
        assert _merge_with_conflict_tagging([], []) == []


# ---------------------------------------------------------------------------
# Re8.1 integration: _fetch_by_title returns confidence + all_candidates
# ---------------------------------------------------------------------------

class TestFetchByTitleRe81Integration:
    """Verify ``_fetch_by_title`` decorates the returned candidate with
    Re8.1 confidence + ranking_reasons + all_candidates fields."""

    @pytest.mark.asyncio
    async def test_fetch_by_title_returns_confidence_field(self):
        """The best candidate dict carries ``confidence`` and ``ranking_reasons``."""
        crossref_hits = [
            {"title": "Just A Title", "authors": ["B"], "doi": "10.2/title",
             "url": "https://doi.org/10.2/title", "year": 2024, "abstract": ""},
        ]
        s2_hits = [
            {"title": "Just A Title", "authors": ["B"], "doi": "10.2/title",
             "url": "https://s2/paper/1", "year": 2024, "abstract": ""},
        ]

        async def mock_crossref(queries, top_k=8, **kwargs):
            return crossref_hits

        async def mock_s2(queries, top_k=8, **kwargs):
            return s2_hits

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            result = await _fetch_by_title("Just A Title", authors=["B"], year=2024)

        assert result is not None
        assert "confidence" in result
        assert result["confidence"] in ("high", "medium", "low")
        assert "ranking_reasons" in result
        assert isinstance(result["ranking_reasons"], list)
        assert len(result["ranking_reasons"]) > 0
        # all_candidates preserves the merged list (1 entry here: same DOI
        # merged crossref + s2 into one)
        assert "all_candidates" in result
        assert len(result["all_candidates"]) >= 1

    @pytest.mark.asyncio
    async def test_fetch_by_title_year_affects_confidence(self):
        """Year mismatch drops the year_consistent reason (no longer in
        ranking_reasons) but does not crash the call."""
        crossref_hits = [
            {"title": "Paper X", "authors": ["A"], "doi": "10.1/x",
             "url": "https://doi.org/10.1/x", "year": 2010, "abstract": ""},
        ]
        s2_hits: list[dict] = []

        async def mock_crossref(queries, top_k=8, **kwargs):
            return crossref_hits

        async def mock_s2(queries, top_k=8, **kwargs):
            return s2_hits

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            # User claims year=2024 but candidate is from 2010 (delta=14)
            result = await _fetch_by_title("Paper X", authors=["A"], year=2024)

        assert result is not None
        # Year conflict should appear as a reason
        assert any("year_conflict" in r for r in result["ranking_reasons"])
        # Year consistent should NOT appear
        assert "year_consistent" not in result["ranking_reasons"]

    @pytest.mark.asyncio
    async def test_fetch_by_title_preserves_conflict_candidates(self):
        """When both sources return title-matching but DOI-less candidates,
        ``all_candidates`` retains both conflict-tagged entries (no drop)."""
        crossref_hits = [
            {"title": "Conflict Paper", "authors": ["A"], "doi": None,
             "url": "https://crossref/x", "year": 2024, "abstract": ""},
        ]
        s2_hits = [
            {"title": "Conflict Paper", "authors": ["B"], "doi": None,
             "url": "https://s2/y", "year": 2024, "abstract": ""},
        ]

        async def mock_crossref(queries, top_k=8, **kwargs):
            return crossref_hits

        async def mock_s2(queries, top_k=8, **kwargs):
            return s2_hits

        with patch(
            "apps.api.app.services.retrieval.adapters.crossref_search.crossref_search",
            new=mock_crossref,
        ), patch(
            "apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_search",
            new=mock_s2,
        ):
            result = await _fetch_by_title("Conflict Paper")

        assert result is not None
        # Both conflict candidates must be preserved in all_candidates
        all_cands = result["all_candidates"]
        assert len(all_cands) == 2
        assert all(c["conflict"] is True for c in all_cands)
        # The returned best is one of the conflict-tagged candidates
        assert result["conflict"] is True


class TestSeedResolverCardRe81Fields:
    """Re8.1 integration: ``seed_resolver_node`` propagates confidence +
    ranking_reasons + all_candidates onto the SeedPaperCard when title
    search succeeds. These fields are optional and must not affect
    schema validation or evidence eligibility."""

    def test_title_seed_card_carries_confidence(self):
        """A title-only seed that resolves via _fetch_by_title must carry
        ``confidence``, ``ranking_reasons``, ``sources`` and ``all_candidates``
        on the resulting card."""
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "online",
            "candidate_seeds": [
                {
                    "seed_id": "s1",
                    "title": "Just A Title",
                    "authors": ["B"],
                    "year": 2024,
                    "role": "classic_anchor",
                },
            ],
        }
        fetched = {
            "title": "Just A Title",
            "authors": ["B"],
            "year": 2024,
            "doi": "10.2/title",
            "canonical_url": "https://doi.org/10.2/title",
            "abstract": "",
            "confidence": "high",
            "ranking_reasons": ["doi_match", "authors_full_match",
                                "title_similarity_1.00", "year_consistent"],
            "sources": ["crossref", "semantic_scholar"],
            "conflict": False,
            "all_candidates": [
                {"title": "Just A Title", "doi": "10.2/title",
                 "confidence": "high", "ranking_reasons": [],
                 "sources": ["crossref", "semantic_scholar"], "conflict": False},
            ],
        }

        async def mock_fetch_by_title(title, authors=None, year=None):
            return fetched

        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_by_title",
            new=mock_fetch_by_title,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 1
        card = cards[0]
        assert card["existence_status"] == "verified"
        # Re8.1 fields propagated
        assert card["confidence"] == "high"
        assert "doi_match" in card["ranking_reasons"]
        assert sorted(card["sources"]) == ["crossref", "semantic_scholar"]
        assert card["conflict"] is False
        assert len(card["all_candidates"]) == 1
        # Card still passes schema validation (new fields are optional)
        from apps.api.app.services.agents.graph.re80_schema import (
            is_seed_evidence_eligible,
        )
        assert is_seed_evidence_eligible(card)
        # Promoted to evidence
        assert len(result["verified_papers"]) == 1


# ---------------------------------------------------------------------------
# Re8.1 WP2 Task 10 — Seed Repair acceptance tests
# ---------------------------------------------------------------------------

import json as _json
from pathlib import Path as _Path
from typing import Any as _Any

_WP2_FIXTURES = _Path(__file__).parent / "fixtures" / "seed_repair_cases.json"


def _load_wp2_cases() -> list[dict[str, _Any]]:
    """Load the 20-case seed repair fixture for WP2 acceptance."""
    with open(_WP2_FIXTURES, encoding="utf-8") as f:
        data = _json.load(f)
    return data["cases"]


_WP2_ALL_CASES = _load_wp2_cases()


def _wp2_cases_by_category(category: str) -> list[dict[str, _Any]]:
    """Filter acceptance fixture cases by category."""
    return [c for c in _WP2_ALL_CASES if c["category"] == category]


def _find_correct_title_for_typo(typo_case: dict[str, _Any]) -> str | None:
    """Recover the correct title for a typo_light case by matching its
    ``resolved_title_contains`` fragment against the exact_title cases."""
    fragment = (typo_case["expected"].get("resolved_title_contains") or "").lower()
    if not fragment:
        return None
    for c in _wp2_cases_by_category("exact_title"):
        if fragment in c["input"]["title"].lower():
            return c["input"]["title"]
    return None


class TestRe81WP2Acceptance:
    """WP2 Task 10: Seed Repair acceptance tests.

    Verifies the four Seed Repair capabilities (title similarity, year
    penalty, confidence computation, conflict tagging) against the
    20-case fixture in ``seed_repair_cases.json``.

    Acceptance criteria (spec.md):
      1. Exact title Top-1 correct rate >= 90% (9/10)
      2. Typo-light title success rate >= 70% (2/3)
      3. Non-existent papers never marked verified (2/2)
      4. Disambiguation correct rate >= 80% (2/3)
      5. Conflict candidates preserve dual-source evidence

    Real Crossref/S2 API calls are not available in the test environment,
    so each criterion is validated via the pure-function capabilities
    (``_title_similarity``, ``_compute_confidence``,
    ``_decide_existence``, ``_merge_with_conflict_tagging``) which are
    the deterministic building blocks of Seed Repair.
    """

    # ── Criterion 1: Exact title Top-1 >= 90% ──────────────────────────

    @pytest.mark.parametrize("case", _wp2_cases_by_category("exact_title"))
    def test_exact_title_top1(self, case):
        """Exact title must yield similarity >= 0.95 and confidence=high.

        Simulates a perfect Crossref/S2 Top-1 hit (same title, DOI
        present, year consistent) and verifies the confidence pipeline
        would promote it to ``verified``.
        """
        title = case["input"]["title"]
        input_year = case["input"].get("year") or 2020

        sim = _title_similarity(title, title)
        assert sim >= 0.95, (
            f"{case['case_id']}: expected self-similarity >= 0.95, got {sim}"
        )

        candidate = {
            "title": title,
            "doi": "10.1000/wp2-acceptance",
            "authors": ["TestAuthor"],
            "year": input_year,
        }
        input_meta = {
            "title": title,
            "authors": ["TestAuthor"],
            "year": input_year,
        }
        level, reasons = _compute_confidence(candidate, input_meta)
        assert level == "high", (
            f"{case['case_id']}: expected high confidence, got {level} "
            f"(reasons={reasons})"
        )

    # ── Criterion 2: Typo-light success rate >= 70% ───────────────────

    def test_typo_light_success_rate(self):
        """Typo-light title success rate >= 70% (>= 2/3).

        A single-character typo must produce similarity >= 0.85 against
        the correct title for at least 2 of 3 cases. Short titles (e.g.
        ResNet's 6-token title) suffer a larger relative Jaccard penalty
        per token difference, so the spec allows 1 failure out of 3.

        The correct title is recovered from the matching exact_title
        case via the ``resolved_title_contains`` fragment.
        """
        threshold = 0.85
        cases = _wp2_cases_by_category("typo_light")
        successes = 0
        details: list[str] = []
        for case in cases:
            correct_title = _find_correct_title_for_typo(case)
            assert correct_title is not None, (
                f"{case['case_id']}: could not recover correct title"
            )
            sim = _title_similarity(case["input"]["title"], correct_title)
            ok = sim >= threshold
            details.append(
                f"{case['case_id']}: sim={sim:.3f} {'PASS' if ok else 'FAIL'}"
            )
            if ok:
                successes += 1
        assert successes >= 2, (
            f"typo success rate {successes}/{len(cases)} < 2/3 "
            f"(threshold={threshold}). Details: {'; '.join(details)}"
        )

    # ── Criterion 3: Non-existent papers never verified ───────────────

    @pytest.mark.parametrize("case", _wp2_cases_by_category("not_found"))
    def test_not_found_never_verified(self, case):
        """Non-existent papers must be marked ``ambiguous`` or
        ``not_found`` — never ``verified``.

        Validates both the fixture's expected constraints and that
        ``_decide_existence`` returns a non-verified status when no
        authoritative source confirms the paper.
        """
        expected = case["expected"]
        assert expected.get("must_not_be_verified") is True, (
            f"{case['case_id']}: fixture missing must_not_be_verified=True"
        )
        allowed = expected.get("allowed_existence_status", [])
        assert "verified" not in allowed, (
            f"{case['case_id']}: allowed statuses must not include 'verified'"
        )
        status, _ = _decide_existence(
            {"title": case["input"]["title"]}, None,
        )
        assert status in ("ambiguous", "not_found"), (
            f"{case['case_id']}: _decide_existence returned '{status}', "
            f"expected ambiguous or not_found"
        )

    # ── Criterion 4: Disambiguation correct rate >= 80% ───────────────

    @pytest.mark.parametrize("case", _wp2_cases_by_category("disambiguation"))
    def test_disambiguation_by_author_year(self, case):
        """Same-title papers must be disambiguated by author + year.

        For ``verified`` cases (disamb_01 GAN/Goodfellow, disamb_03
        AlexNet/Krizhevsky): correct authors → ``high`` confidence.

        For ``ambiguous`` case (disamb_02 Transformer/Smith): the user
        claims a wrong author. A real Crossref hit carries the actual
        authors (Vaswani et al.); ``_compute_confidence`` must detect
        the author mismatch and drop to ``medium`` or ``low``.
        """
        title = case["input"]["title"]
        user_authors = case["input"]["authors"]
        year = case["input"]["year"]
        expected_status = case["expected"]["existence_status"]

        if expected_status == "verified":
            # Correct authors + DOI + title + year → high
            candidate = {
                "title": title,
                "doi": "10.1000/disamb-correct",
                "authors": user_authors,
                "year": year,
            }
            input_meta = {
                "title": title,
                "authors": user_authors,
                "year": year,
            }
            level, reasons = _compute_confidence(candidate, input_meta)
            assert level == "high", (
                f"{case['case_id']}: correct disambiguation should yield "
                f"high, got {level} (reasons={reasons})"
            )
        else:
            # disamb_02: user claims "Smith" but the real paper is by
            # Vaswani et al. Simulate a real Crossref hit with the true
            # authors; the user's wrong author must NOT produce high.
            real_authors = ["Vaswani", "Shazeer", "Parmar"]
            candidate_real = {
                "title": title,
                "doi": "10.5555/3295222.3295349",
                "authors": real_authors,
                "year": year,
            }
            input_meta_wrong = {
                "title": title,
                "authors": user_authors,  # ["Smith"]
                "year": year,
            }
            level, reasons = _compute_confidence(
                candidate_real, input_meta_wrong,
            )
            assert level in ("medium", "low"), (
                f"{case['case_id']}: wrong author should yield medium/low, "
                f"got {level} (reasons={reasons})"
            )

    # ── Criterion 5: Conflict evidence preserved ──────────────────────

    def test_conflict_evidence_preserved_different_doi(self):
        """Same title + different DOIs across sources → both candidates
        retained (no silent drop), dual-source evidence visible.

        ``_merge_with_conflict_tagging`` treats different-DOI candidates
        as independent results (``conflict=False``). The ``conflict=True``
        tag is reserved for the no-DOI title-match scenario (see
        ``test_conflict_evidence_preserved_no_doi``). The acceptance
        criterion here is that neither candidate is silently dropped
        and both sources remain visible in the merged output.
        """
        crossref_cands = [
            {"doi": "10.1/a", "title": "Same Title",
             "authors": ["A"], "year": 2024},
        ]
        s2_cands = [
            {"doi": "10.2/b", "title": "Same Title",
             "authors": ["B"], "year": 2024},
        ]
        merged = _merge_with_conflict_tagging(
            crossref_cands, s2_cands, input_title="Same Title",
        )
        # Both candidates retained (no silent drop)
        assert len(merged) == 2, (
            f"expected 2 candidates (no silent drop), got {len(merged)}"
        )
        # Dual-source evidence preserved
        all_sources: set[str] = set()
        for c in merged:
            all_sources.update(c.get("sources", []))
        assert "crossref" in all_sources, "crossref evidence missing"
        assert "semantic_scholar" in all_sources, (
            "semantic_scholar evidence missing"
        )

    def test_conflict_evidence_preserved_no_doi(self):
        """Same title + no DOI on either side → both candidates retained,
        ``conflict=True`` and ``conflict_type='title_match_doi_mismatch'``."""
        crossref_cands = [
            {"doi": None, "title": "GAN Paper",
             "authors": ["A"], "year": 2024},
        ]
        s2_cands = [
            {"doi": None, "title": "GAN Paper",
             "authors": ["B"], "year": 2024},
        ]
        merged = _merge_with_conflict_tagging(
            crossref_cands, s2_cands, input_title="GAN Paper",
        )
        assert len(merged) == 2
        for c in merged:
            assert c["conflict"] is True
            assert c["conflict_type"] == "title_match_doi_mismatch"
