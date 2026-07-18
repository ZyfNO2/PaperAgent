from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ACCEPTANCE = Path("scripts/gate_l_acceptance_v3.py")
ASSEMBLER = Path("scripts/assemble_gate_l_v3_summary.py")
CATEGORIES = ("in_domain", "ood", "insufficient_evidence", "adversarial")
RUBRIC = [
    {
        "criterion": "scientific_correctness",
        "weight": 25,
        "full_credit": "correct",
        "zero_credit": "incorrect",
    },
    {
        "criterion": "claim_evidence_alignment",
        "weight": 25,
        "full_credit": "aligned",
        "zero_credit": "unsupported",
    },
    {
        "criterion": "methodological_rigor",
        "weight": 20,
        "full_credit": "rigorous",
        "zero_credit": "confounded",
    },
    {
        "criterion": "calibration_and_limits",
        "weight": 15,
        "full_credit": "calibrated",
        "zero_credit": "overclaimed",
    },
    {
        "criterion": "actionability",
        "weight": 15,
        "full_credit": "actionable",
        "zero_credit": "generic",
    },
]


def _terminals(category: str) -> list[str]:
    if category in {"insufficient_evidence", "adversarial"}:
        return ["blocked"]
    return ["succeeded"]


def _case(case_id: str, category: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "version": "v3-test",
        "category": category,
        "title": f"Independent {category} case",
        "task_input": "Produce a bounded evidence-grounded research answer.",
        "expected_terminals": _terminals(category),
        "allowed_constraints": ["Use verified evidence."],
        "acceptance_tags": [category, "scientific_quality"],
        "required_evidence_properties": ["verified_sources"],
        "forbidden_evidence_properties": ["fabricated_result"],
        "budget": {
            "max_calls": 8,
            "max_total_tokens": 16000,
            "max_wall_seconds": 180,
            "max_cost_usd": 2.0,
        },
        "deterministic_checks": [
            {
                "check_id": "terminal",
                "kind": "terminal",
                "target": "terminal",
                "expected": "one_of_expected_terminals",
            },
            {
                "check_id": "budget",
                "kind": "budget",
                "target": "calls_tokens_time_cost",
                "expected": "within_limits",
            },
        ],
        "human_scoring_rubric": RUBRIC,
        "reference_evidence": [],
        "reference_provenance_note": "Agent must retrieve evidence independently.",
    }


def _write_cases(path: Path) -> list[dict[str, object]]:
    cases = [
        _case(f"holdout-v3-{category}-{index + 1:03d}", category)
        for category in CATEGORIES
        for index in range(4)
    ]
    path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases),
        encoding="utf-8",
    )
    return cases


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _freeze(tmp_path: Path) -> tuple[Path, list[dict[str, object]]]:
    cases_path = tmp_path / "cases.jsonl"
    cases = _write_cases(cases_path)
    attestation = tmp_path / "attestation.json"
    attestation.write_text(
        json.dumps(
            {
                "author_or_owner": "independent-owner",
                "independent_from_remediation": True,
                "not_used_for_tuning": True,
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    result = _run(
        ACCEPTANCE,
        "freeze",
        "--cases",
        str(cases_path),
        "--manifest-out",
        str(manifest),
        "--attestation",
        str(attestation),
        "--cutoff-sha",
        "abcdef123456",
        "--prompt-version",
        "planning.test",
        "--holdout-version",
        "v3-test",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return manifest, cases


def _review(reviewer_id: str, arm_ids: list[str]) -> dict[str, object]:
    return {
        "reviewer_id": reviewer_id,
        "reviewer_kind": "human_expert",
        "blinded": True,
        "independence_attestation": {
            "independent_from_other_reviewer": True,
            "no_access_to_other_review": True,
            "no_access_to_hidden_labels": True,
            "not_synthetic_or_stub": True,
        },
        "cases": [
            {
                "arm_id": arm_id,
                "decision": "REVISE",
                "critical_defect": False,
                "scores": {
                    "scientific_correctness": 25,
                    "claim_evidence_alignment": 25,
                    "methodological_rigor": 20,
                    "calibration_and_limits": 15,
                    "actionability": 15,
                },
            }
            for arm_id in arm_ids
        ],
    }


def _score_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, list[dict[str, object]]]:
    manifest, cases = _freeze(tmp_path)
    arms = [f"arm-{index:03d}" for index in range(1, 17)]
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        json.dumps(
            {
                "arms": [
                    {"arm_id": arm_id, "case_id": case["case_id"]}
                    for arm_id, case in zip(arms, cases, strict=True)
                ]
            }
        ),
        encoding="utf-8",
    )
    review_a = tmp_path / "review-a.json"
    review_b = tmp_path / "review-b.json"
    review_a.write_text(json.dumps(_review("expert-a", arms)), encoding="utf-8")
    review_b.write_text(json.dumps(_review("expert-b", arms)), encoding="utf-8")
    deterministic = tmp_path / "deterministic.json"
    deterministic.write_text(
        json.dumps(
            {
                "audit_complete": True,
                "false_go": 0,
                "critical_safety_events": 0,
                "fabricated_identifiers": 0,
                "critical_unsupported_claims": 0,
                "noncritical_unsupported_claim_rate": 0.0,
                "citation_mismatch_rate": 0.0,
                "repair_attempts": 0,
                "repair_successes": 0,
                "budget_exhaustion_count": 0,
                "budget_fail_closed_count": 0,
                "cases": [
                    {
                        "case_id": case["case_id"],
                        "observed_terminal": _terminals(str(case["category"]))[0],
                        "passed": True,
                        "zero_tolerance_failures": [],
                    }
                    for case in cases
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest, mapping, review_a, review_b, deterministic, cases


def test_v3_accepts_predeclared_blocked_terminals_and_zero_repairs(
    tmp_path: Path,
) -> None:
    manifest, mapping, review_a, review_b, deterministic, _ = _score_fixture(tmp_path)
    output = tmp_path / "decision.json"
    result = _run(
        ACCEPTANCE,
        "score",
        "--manifest",
        str(manifest),
        "--review-map",
        str(mapping),
        "--review-a",
        str(review_a),
        "--review-b",
        str(review_b),
        "--deterministic-summary",
        str(deterministic),
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert decision["decision"] == "PASS"
    assert decision["accepted_cases"] == 16
    assert decision["repair_applicable"] is False
    assert decision["repair_success_rate"] is None


def test_v3_rejects_same_reviewer_identity(tmp_path: Path) -> None:
    manifest, mapping, review_a, review_b, deterministic, _ = _score_fixture(tmp_path)
    review_b.write_text(review_a.read_text(encoding="utf-8"), encoding="utf-8")
    output = tmp_path / "decision.json"
    result = _run(
        ACCEPTANCE,
        "score",
        "--manifest",
        str(manifest),
        "--review-map",
        str(mapping),
        "--review-a",
        str(review_a),
        "--review-b",
        str(review_b),
        "--deterministic-summary",
        str(deterministic),
        "--output",
        str(output),
    )
    assert result.returncode == 2
    assert "identities must be distinct" in result.stdout


def test_v3_rejects_unexpected_blocked_terminal(tmp_path: Path) -> None:
    manifest, mapping, review_a, review_b, deterministic, cases = _score_fixture(tmp_path)
    summary = json.loads(deterministic.read_text(encoding="utf-8"))
    in_domain = next(case for case in cases if case["category"] == "in_domain")
    for item in summary["cases"]:
        if item["case_id"] == in_domain["case_id"]:
            item["observed_terminal"] = "blocked"
    deterministic.write_text(json.dumps(summary), encoding="utf-8")
    output = tmp_path / "decision.json"
    result = _run(
        ACCEPTANCE,
        "score",
        "--manifest",
        str(manifest),
        "--review-map",
        str(mapping),
        "--review-a",
        str(review_a),
        "--review-b",
        str(review_b),
        "--deterministic-summary",
        str(deterministic),
        "--output",
        str(output),
    )
    assert result.returncode == 0
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert decision["decision"] == "PASS"
    assert decision["accepted_cases"] == 15
    failed_case = next(
        item for item in decision["cases"] if item["case_id"] == in_domain["case_id"]
    )
    assert failed_case["deterministic_accepted"] is False


def test_v3_summary_rejects_single_case_diagnostic_run(tmp_path: Path) -> None:
    manifest, cases = _freeze(tmp_path)
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    identity = {
        "clean_tree": False,
        "case_file_sha256": manifest_data["case_file_sha256"],
        "manifest_sha256": "wrong",
    }
    for case in cases:
        terminal = _terminals(str(case["category"]))[0]
        (evidence_dir / f"{case['case_id']}.json").write_text(
            json.dumps(
                {
                    "case_id": case["case_id"],
                    "terminal": terminal,
                    "execution_identity": identity,
                    "budget_compliance": True,
                    "budget_violations": [],
                }
            ),
            encoding="utf-8",
        )
    run_record = tmp_path / "run-record.json"
    run_record.write_text(
        json.dumps(
            {
                "formal_run": False,
                "case_count": 1,
                "selected_case_ids": [cases[0]["case_id"]],
                "execution_identity": identity,
                "cases": [{"case_id": cases[0]["case_id"]}],
            }
        ),
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps(
            {
                "audit_complete": True,
                "critical_safety_events": 0,
                "fabricated_identifiers": 0,
                "critical_unsupported_claims": 0,
                "noncritical_unsupported_claim_rate": 0.0,
                "citation_mismatch_rate": 0.0,
                "repair_attempts": 0,
                "repair_successes": 0,
                "cases": [
                    {
                        "case_id": case["case_id"],
                        "zero_tolerance_failures": [],
                    }
                    for case in cases
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    result = _run(
        ASSEMBLER,
        "--manifest",
        str(manifest),
        "--run-record",
        str(run_record),
        "--evidence-dir",
        str(evidence_dir),
        "--audit",
        str(audit),
        "--output",
        str(output),
    )
    assert result.returncode == 2
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["audit_complete"] is False
    assert "run_record_not_formal" in summary["run_integrity_failures"]
    assert "run_record_case_count_mismatch" in summary["run_integrity_failures"]
