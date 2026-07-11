"""Re5.X: SourceCatalog + search models + query_ledger tests."""
from __future__ import annotations

import os
import pytest

from apps.api.app.services.search_catalog import (
    get_source_catalog, reset_source_catalog,
)
from apps.api.app.services.source_policy import reset_source_policy
from apps.api.app.services.agents.graph.schemas.search_models import (
    SourceResult, SearchCard, Diagnosis, CoverageGate,
)
from apps.api.app.services.agents.graph.validators.query_ledger import (
    QueryLedger, _fingerprint,
)


class TestSourceCatalog:
    def test_allowed_sources_excludes_disabled(self):
        """Disabled sources should not appear in allowed_sources."""
        os.environ["TEST_MODE"] = "1"
        os.environ["RATE_LIMITED_SOURCES_DISABLED"] = "1"
        reset_source_policy()
        reset_source_catalog()
        cat = get_source_catalog()
        names = cat.allowed_source_names()
        assert "semantic_scholar" not in names
        assert "openalex" not in names
        assert "arxiv" in names
        del os.environ["TEST_MODE"]
        del os.environ["RATE_LIMITED_SOURCES_DISABLED"]
        reset_source_policy()
        reset_source_catalog()

    def test_pubmed_only_for_medical(self):
        """PubMed should only appear for medical domains."""
        os.environ["RATE_LIMITED_SOURCES_DISABLED"] = "0"
        reset_source_policy()
        reset_source_catalog()
        cat = get_source_catalog()
        non_medical = cat.allowed_source_names("computer vision")
        assert "pubmed" not in non_medical
        medical = cat.allowed_source_names("medical_ai")
        assert "pubmed" in medical
        del os.environ["RATE_LIMITED_SOURCES_DISABLED"]
        reset_source_policy()
        reset_source_catalog()

    def test_no_removed_sources(self):
        """web/scholar/google must never appear."""
        cat = get_source_catalog()
        for domain in ["", "medical", "computer vision", "unknown"]:
            names = cat.allowed_source_names(domain)
            assert "web" not in names
            assert "scholar" not in names

    def test_alternate_source(self):
        """Failed source should have an alternate."""
        cat = get_source_catalog()
        assert cat.get_alternate("semantic_scholar") == "crossref"
        assert cat.get_alternate("openalex") == "crossref"

    def test_source_list_for_prompt(self):
        """Prompt source list should only contain allowed sources."""
        cat = get_source_catalog()
        text = cat.source_list_for_prompt("")
        assert "arxiv" in text
        # Should not contain 'web'
        assert "web:" not in text.lower()


class TestSourceResult:
    def test_success_status(self):
        r = SourceResult(source="arxiv", query="test", status="success", n_raw=5)
        assert r.status == "success"
        assert not r.is_empty_not_failed

    def test_empty_not_failed(self):
        r = SourceResult(source="arxiv", query="test", status="empty")
        assert r.is_empty_not_failed

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            SourceResult(source="arxiv", query="test", status="bogus")


class TestSearchCard:
    def test_valid_card(self):
        c = SearchCard(card_id="sc-001", source="arxiv", query="YOLO detection")
        assert c.target_role == "core"

    def test_invalid_role_rejected(self):
        with pytest.raises(Exception):
            SearchCard(card_id="sc-1", source="arxiv", query="test", target_role="bogus")

    def test_empty_query_rejected(self):
        with pytest.raises(Exception):
            SearchCard(card_id="sc-1", source="arxiv", query="")


class TestDiagnosis:
    def test_valid_diagnosis(self):
        d = Diagnosis(
            diagnosis_id="d1", diagnosis_code="role_gap", confidence=0.8,
            action="rewrite_query", target_role="baseline", evidence_ids=["c1"],
        )
        assert d.diagnosis_code == "role_gap"

    def test_invalid_code_rejected(self):
        with pytest.raises(Exception):
            Diagnosis(diagnosis_id="d1", diagnosis_code="bogus", confidence=0.5,
                      action="rewrite_query", evidence_ids=["c1"])

    def test_empty_evidence_ids_rejected(self):
        with pytest.raises(Exception):
            Diagnosis(diagnosis_id="d1", diagnosis_code="role_gap", confidence=0.5,
                      action="rewrite_query", evidence_ids=[])


class TestQueryLedger:
    def test_add_and_fingerprint(self):
        ledger = QueryLedger()
        entry = ledger.add(round=1, card_id="sc-001", source="arxiv", query="YOLO detection")
        assert entry["fingerprint"] is not None
        assert len(entry["fingerprint"]) == 16

    def test_duplicate_fingerprint_rejected(self):
        ledger = QueryLedger()
        ledger.add(round=1, card_id="sc-001", source="arxiv", query="YOLO detection")
        with pytest.raises(ValueError, match="Duplicate"):
            ledger.add(round=2, card_id="sc-002", source="arxiv", query="YOLO detection")

    def test_has_fingerprint(self):
        ledger = QueryLedger()
        ledger.add(round=1, card_id="sc-001", source="arxiv", query="YOLO detection")
        assert ledger.has_fingerprint("arxiv", "YOLO detection")
        assert not ledger.has_fingerprint("arxiv", "different query")

    def test_fingerprint_normalization(self):
        """Same query with different whitespace/punctuation should have same fingerprint."""
        fp1 = _fingerprint("arxiv", "YOLO  detection!!")
        fp2 = _fingerprint("arxiv", "yolo detection")
        assert fp1 == fp2

    def test_stats(self):
        ledger = QueryLedger()
        ledger.add(round=1, card_id="sc-1", source="arxiv", query="a", source_status="success")
        ledger.add(round=1, card_id="sc-2", source="github", query="b", source_status="empty")
        stats = ledger.stats()
        assert stats["n_total"] == 2
        assert stats["by_status"]["success"] == 1
        assert stats["by_status"]["empty"] == 1


class TestCoverageGate:
    def test_pass_when_all_required_met(self):
        gate = CoverageGate(
            required_roles={"core": 2, "baseline": 1},
            current_coverage={"core": 3, "baseline": 2},
            budget_remaining=5,
            decision="pass",
        )
        assert gate.decision == "pass"
        assert gate.gaps == []

    def test_reflect_when_gap_exists(self):
        gate = CoverageGate(
            required_roles={"core": 2, "baseline": 1},
            current_coverage={"core": 1, "baseline": 0},
            gaps=["baseline"],
            budget_remaining=3,
            decision="reflect",
        )
        assert "baseline" in gate.gaps
