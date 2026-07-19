from __future__ import annotations

from pathlib import Path

from paperagent.gold_case import run_gold_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_npc_gold_case_passes_without_claiming_scientific_acceptance() -> None:
    report = run_gold_case(REPOSITORY_ROOT)

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


def test_npc_gold_case_digest_is_deterministic() -> None:
    first = run_gold_case(REPOSITORY_ROOT)
    second = run_gold_case(REPOSITORY_ROOT)

    assert first.report_digest == second.report_digest
    assert first.model_dump() == second.model_dump()
