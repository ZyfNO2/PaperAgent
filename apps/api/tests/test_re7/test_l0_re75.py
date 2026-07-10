"""Re7.5 Full-chain verification — L0 tests for ChangeHypothesis, taxonomy, harness."""
from __future__ import annotations

import pytest


class TestChangeHypothesis:
    def test_valid_hypothesis(self):
        from apps.api.app.services.eval_harness import ChangeHypothesis
        ch = ChangeHypothesis(
            round=1,
            failure_signature="json_field_drift",
            hypothesis="add node-specific validator",
            change_scope=["novelty_review.py"],
            expected_gain="reduce field drift by 90%",
            must_not_regress=["accepted papers unchanged"],
            target_tests=["XD-01", "XD-06"],
        )
        assert ch.round == 1
        assert ch.result == "pending"

    def test_change_scope_required(self):
        from apps.api.app.services.eval_harness import ChangeHypothesis
        ch = ChangeHypothesis(
            round=1, failure_signature="test",
            hypothesis="h", expected_gain="gain",
            must_not_regress=["x"], target_tests=["t"],
        )
        assert ch.change_scope == []


class TestCrossDomainResult:
    def test_matching_verdict(self):
        from apps.api.app.services.eval_harness import CrossDomainResult
        r = CrossDomainResult(
            case_id="XD-01",
            expected_verdict="GO", actual_verdict="GO",
            verdict_match=True, has_evidence=True,
            baseline_count=3, paper_count=12,
        )
        assert r.verdict_match
        assert not r.has_fabrication

    def test_mismatch_verdict(self):
        from apps.api.app.services.eval_harness import CrossDomainResult
        r = CrossDomainResult(
            case_id="XD-04",
            expected_verdict="RISKY", actual_verdict="GO",
            verdict_match=False, has_evidence=True,
            baseline_count=2, paper_count=8,
            errors=["underestimated risk"],
        )
        assert not r.verdict_match
        assert len(r.errors) == 1


class TestRoundReport:
    def test_valid_report(self):
        from apps.api.app.services.eval_harness import RoundReport
        report = RoundReport(
            round=0, run_id="baseline-001",
            total_cases=10, passed=8, failed=2,
            p0_pass=True,
            decision="HOLD",
        )
        assert report.decision == "HOLD"

    def test_p0_fails_degrades_report(self):
        from apps.api.app.services.eval_harness import RoundReport
        report = RoundReport(
            round=0, run_id="r1", total_cases=10,
            passed=7, failed=3,
            p0_pass=False,
            decision="NO_GO",
        )
        assert report.decision == "NO_GO"
        assert not report.p0_pass


class TestFailureTaxonomy:
    def test_valid_taxonomy(self):
        from apps.api.app.services.eval_harness import FailureTaxonomy
        ft = FailureTaxonomy(
            run_id="r1",
            total_failures=5,
            by_signature={"json_field_drift": 2, "rag_no_citation": 3},
            by_severity={"high": 2, "medium": 3},
            by_module={"novelty_review": 2, "rag_retriever": 3},
        )
        assert ft.total_failures == 5
        assert ft.by_signature["json_field_drift"] == 2


class TestFailureSignatures:
    def test_signatures_complete(self):
        from apps.api.app.services.eval_harness import FAILURE_SIGNATURES
        expected = {
            "json_field_drift", "empty_repair", "empty_expansion",
            "cross_domain_misjudge", "novelty_pseudo_innovation",
            "rag_no_citation", "rag_fabrication", "rag_abstain_fail",
            "job_stuck", "job_cancel_fail", "budget_exceed_no_partial",
            "feedback_leak", "provider_drift", "fallback_hidden",
        }
        assert set(FAILURE_SIGNATURES.keys()) == expected
