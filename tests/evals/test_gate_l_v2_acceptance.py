from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/gate_l_v2_acceptance.py")
CATEGORIES = ("in_domain", "ood", "insufficient_evidence", "adversarial")
RUBRIC = [
    {
        "criterion": "scientific_correctness",
        "weight": 25,
        "full_credit": "correct",
        "zero_credit": "material error",
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


def _case(case_id: str, category: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "version": "v2",
        "category": category,
        "title": f"Case {case_id}",
        "task_input": "Produce a bounded evidence-grounded research answer.",
        "expected_terminal": "succeeded",
        "allowed_constraints": ["Use verifiable evidence."],
        "acceptance_tags": ["scientific_quality"],
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
                "expected": "succeeded",
            },
            {
                "check_id": "budget",
                "kind": "budget",
                "target": "calls_tokens_time_cost",
                "expected": "within_limits",
            },
        ],
        "human_scoring_rubric": RUBRIC,
        "reference_evidence": [
            {
                "claim_scope": "test provenance",
                "source_type": "journal_article",
                "stable_identifier": "10.0000/example",
                "title": "Example primary source",
            }
        ],
    }


def _write_cases(path: Path) -> list[dict[str, object]]:
    cases = [
        _case(f"holdout-v2-{category}-{index + 1:03d}", category)
        for category in CATEGORIES
        for index in range(4)
    ]
    path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases),
        encoding="utf-8",
    )
    return cases


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _freeze(tmp_path: Path) -> tuple[Path, Path, list[dict[str, object]]]:
    cases_path = tmp_path / "holdout_cases.v2.jsonl"
    cases = _write_cases(cases_path)
    attestation = tmp_path / "attestation.json"
    attestation.write_text(
        json.dumps(
            {
                "author_or_owner": "independent-review-owner",
                "independent_from_remediation": True,
                "not_used_for_tuning": True,
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "holdout_manifest.v2.json"
    result = _run(
        "freeze",
        "--cases",
        str(cases_path),
        "--manifest-out",
        str(manifest),
        "--attestation",
        str(attestation),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return manifest, cases_path, cases


def test_gate_l_v2_validate_and_freeze_records_digest(tmp_path: Path) -> None:
    manifest_path, cases_path, _ = _freeze(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "frozen_pending_execution"
    assert manifest["version"] == "v2"
    assert manifest["expected_case_count"] == 16
    assert manifest["case_file"] == cases_path.as_posix()
    assert len(manifest["case_file_sha256"]) == 64
    assert manifest["scientific_behavior_cutoff_sha"].startswith("d4fef014")

    verified = _run("verify", "--manifest", str(manifest_path))
    assert verified.returncode == 0, verified.stdout + verified.stderr


def test_gate_l_v2_verify_rejects_tampered_frozen_cases(tmp_path: Path) -> None:
    manifest_path, cases_path, _ = _freeze(tmp_path)
    cases_path.write_text(cases_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = _run("verify", "--manifest", str(manifest_path))

    assert result.returncode == 2
    assert "digest mismatch" in result.stdout


def test_gate_l_v2_validate_rejects_wrong_category_counts(tmp_path: Path) -> None:
    cases_path = tmp_path / "bad.jsonl"
    cases = _write_cases(cases_path)
    cases[-1]["category"] = "in_domain"
    cases_path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases),
        encoding="utf-8",
    )

    result = _run("validate", "--cases", str(cases_path))

    assert result.returncode == 2
    assert "category counts" in result.stdout


def test_gate_l_v2_blinded_package_excludes_provider_identity(tmp_path: Path) -> None:
    manifest_path, _, cases = _freeze(tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    for case in cases:
        (evidence_dir / f"{case['case_id']}.json").write_text(
            json.dumps(
                {
                    "case_id": case["case_id"],
                    "terminal": "succeeded",
                    "execution_identity": {
                        "provider": "secret-provider-name",
                        "model": "secret-model-name",
                    },
                    "review_output": {"report": {"summary": "review me"}},
                }
            ),
            encoding="utf-8",
        )
    output = tmp_path / "blind.json"

    result = _run(
        "blind",
        "--manifest",
        str(manifest_path),
        "--evidence-dir",
        str(evidence_dir),
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    raw = output.read_text(encoding="utf-8")
    assert "secret-provider-name" not in raw
    assert "secret-model-name" not in raw
    assert "expected_terminal" not in raw


def _review(cases: list[dict[str, object]], terminal: str = "succeeded") -> dict[str, object]:
    return {
        "reviewer_id": "reviewer",
        "blinded": True,
        "cases": [
            {
                "case_id": case["case_id"],
                "terminal_decision": terminal,
                "critical_defect": False,
                "scores": {
                    "scientific_correctness": 25,
                    "claim_evidence_alignment": 25,
                    "methodological_rigor": 20,
                    "calibration_and_limits": 15,
                    "actionability": 15,
                },
            }
            for case in cases
        ],
    }


def test_gate_l_v2_score_passes_only_complete_hard_gates(tmp_path: Path) -> None:
    manifest_path, _, cases = _freeze(tmp_path)
    review_a = tmp_path / "a.json"
    review_b = tmp_path / "b.json"
    review_a.write_text(json.dumps(_review(cases)), encoding="utf-8")
    review_b.write_text(json.dumps(_review(cases)), encoding="utf-8")
    deterministic = tmp_path / "deterministic.json"
    deterministic.write_text(
        json.dumps(
            {
                "false_go": 0,
                "critical_safety_events": 0,
                "fabricated_identifiers": 0,
                "critical_unsupported_claims": 0,
                "noncritical_unsupported_claim_rate": 0.0,
                "citation_mismatch_rate": 0.0,
                "repair_success_rate": 1.0,
                "budget_fail_closed_rate": 1.0,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "decision.json"

    result = _run(
        "score",
        "--manifest",
        str(manifest_path),
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
    assert decision["cohen_kappa"] == 1.0
