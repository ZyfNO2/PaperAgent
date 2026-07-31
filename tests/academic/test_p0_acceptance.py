from __future__ import annotations

import pytest

from paperagent.academic.p0_acceptance import (
    P0AcceptanceError,
    assert_protocol_compatible,
    build_blocked_report,
    decide_p0,
    score_accepted_context,
    score_artifacts,
    score_claims,
    validate_denominators,
    verify_file_digest,
)


def test_accepted_only_context_and_claim_failures_are_classified() -> None:
    context = score_accepted_context(
        (
            {"evidence_id": "a", "status": "accepted"},
            {"evidence_id": "b", "status": "conflicted"},
            {"evidence_id": "c", "status": "rejected"},
        )
    )
    assert context["accepted_only_violation"] == 2
    assert context["conflicted_leakage"] == 1
    assert context["rejected_leakage"] == 1

    claims = score_claims(
        (
            {
                "supported": True,
                "evidence_ids": ["a"],
                "citation_match": True,
                "severity": "major",
            },
            {
                "supported": False,
                "evidence_ids": ["b"],
                "citation_match": False,
                "critical": True,
            },
        ),
        {"a"},
    )
    assert claims["unsupported_claim_count"] == 1
    assert claims["critical_unsupported_claim_count"] == 1
    assert claims["citation_mismatch_count"] == 1
    assert claims["critical_citation_mismatch_count"] == 1


def test_missing_gate_cannot_become_go_or_zero_metrics() -> None:
    result = decide_p0(
        "GO",
        {"real_papers": "PASS", "human_gold_labels": "BLOCKED"},
        critical_unsupported_claims=None,
        critical_citation_mismatches=None,
        false_go=None,
    )
    assert result["overall_decision"] == "REVISE"
    assert result["p0_release"] == "NO-GO"
    assert result["false_go"] == 1
    assert result["critical_metrics_complete"] is False


def test_denominator_and_protocol_mismatch_fail_closed() -> None:
    with pytest.raises(P0AcceptanceError, match="denominator"):
        validate_denominators({"questions": 31}, {"questions": 32})
    with pytest.raises(P0AcceptanceError, match="protocol"):
        assert_protocol_compatible(
            (
                {
                    "protocol_version": "academic-rag-p0-scientific-acceptance.v1",
                    "schema_digest": "a",
                    "golden_fixture_digest": "b",
                },
                {
                    "protocol_version": "academic-rag-p0-scientific-acceptance.v2",
                    "schema_digest": "a",
                    "golden_fixture_digest": "b",
                },
            )
        )


def test_artifacts_require_all_eight_types_and_independent_review() -> None:
    result = score_artifacts(
        (
            {
                "artifact_type": "evidence_bundle",
                "schema_valid": True,
                "required_fields_complete": True,
                "claim_evidence_coverage": True,
                "revision_traceable": True,
            },
        ),
        reviewer_approved=False,
    )
    assert result["status"] == "BLOCKED"
    assert len(result["missing_artifacts"]) == 7


def test_initial_report_is_revise_and_p0_no_go() -> None:
    report = build_blocked_report(
        {
            "protocol_version": "academic-rag-p0-scientific-acceptance.v1",
            "schema_digest": "a",
            "golden_fixture_digest": "b",
            "starting_commit_pair": {"paperagent": "a", "paperclaw": "b"},
        }
    )
    assert report["overall_decision"] == "REVISE"
    assert report["p0_release"] == "NO-GO"
    assert report["metrics"]["critical_unsupported_claims"] is None


def test_resource_digest_mismatch_is_rejected(tmp_path) -> None:
    resource = tmp_path / "resource.json"
    resource.write_text("{}", encoding="utf-8")
    with pytest.raises(P0AcceptanceError, match="digest mismatch"):
        verify_file_digest(resource, "0" * 64)
