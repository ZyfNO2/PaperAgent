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
    _classify_input,
    _decide_existence,
    _titles_agree,
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
            ],
        }
        real_fetched = {
            "title": "Real", "authors": ["A"], "doi": "10.1/real",
            "canonical_url": "https://doi.org/10.1/real",
        }

        async def mock_crossref(doi):
            if doi == "10.1/real":
                return real_fetched
            return None

        with patch(
            "apps.api.app.services.agents.graph.nodes.seed_resolver._fetch_crossref",
            new=mock_crossref,
        ):
            result = seed_resolver_node(state)

        cards = result["seed_cards"]
        assert len(cards) == 3
        statuses = {c["seed_id"]: c["existence_status"] for c in cards}
        assert statuses["real"] == "verified"
        assert statuses["fake"] in ("ambiguous", "not_found")
        assert statuses["titleonly"] == "ambiguous"
        # Only the real one promoted
        assert len(result["verified_papers"]) == 1
        assert result["verified_papers"][0]["seed_id"] == "real"
        # 3 ledger entries
        assert len(result["reasoning_ledger"]) == 3


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
