from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from paperagent.gold_case import GoldCaseReport, _build_rag_input, run_gold_case

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_npc_gold_case_passes_without_claiming_scientific_acceptance() -> None:
    report = run_gold_case(REPOSITORY_ROOT)

    assert report.contract_version == "paperagent.gold-case.v2"
    assert report.status == "passed"
    assert report.proposal_decision == "GO"
    assert report.audit_verdict == "GO"
    assert report.grade_passed is True
    assert report.grade_score >= report.minimum_score
    assert report.evidence_scope == "synthetic_evaluation"
    assert report.scientific_release_ready is False
    assert report.scientific_claim == "not_claimed"
    assert report.rag.recall_at_k["5"] == 1.0
    assert report.rag.citation_support_rate == 1.0
    assert report.rag.unsupported_claim_rate == 0.0
    assert all(report.acceptance_checks.values())
    assert len(report.report_digest) == 64


def test_baseline_reproduction_is_not_counted_as_literature_citation_support() -> None:
    evaluation = _build_rag_input(REPOSITORY_ROOT / "evals" / "academic_tailoring" / "npc")

    assert "baseline-reproduction" not in {claim.claim_id for claim in evaluation.claims}
    assert all(claim.claim_id.startswith(("module-", "comparison-")) for claim in evaluation.claims)


def test_npc_gold_case_digest_is_deterministic() -> None:
    first = run_gold_case(REPOSITORY_ROOT)
    second = run_gold_case(REPOSITORY_ROOT)

    assert first.report_digest == second.report_digest
    assert first.model_dump() == second.model_dump()


def test_gold_case_report_rejects_tampered_payload() -> None:
    payload = run_gold_case(REPOSITORY_ROOT).model_dump(mode="json")
    payload["limitations"][0] = "tampered limitation"

    with pytest.raises(ValidationError, match="digest mismatch"):
        GoldCaseReport.model_validate(payload)


def test_gold_case_report_rejects_missing_acceptance_check() -> None:
    payload = run_gold_case(REPOSITORY_ROOT).model_dump(mode="json")
    del payload["acceptance_checks"]["scientific_release_not_claimed"]

    with pytest.raises(ValidationError, match="check set is incomplete"):
        GoldCaseReport.model_validate(payload)
