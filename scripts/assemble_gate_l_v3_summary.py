"""Assemble a fail-closed deterministic summary from Gate L v3 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from gate_l_acceptance_v3 import allowed_terminals, verify_manifest


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_cases(audit: dict[str, Any], expected: set[str]) -> dict[str, list[str]]:
    raw = audit.get("cases")
    if not isinstance(raw, list):
        raise ValueError("audit.cases must be a list")
    result: dict[str, list[str]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
            raise ValueError("invalid audit case")
        case_id = item["case_id"]
        failures = item.get("zero_tolerance_failures")
        if case_id in result or not isinstance(failures, list):
            raise ValueError(f"invalid audit entry for {case_id}")
        if any(not isinstance(value, str) or not value for value in failures):
            raise ValueError(f"invalid audit failure for {case_id}")
        result[case_id] = failures
    if set(result) != expected:
        raise ValueError("audit must cover the exact frozen case set")
    return result


def assemble(
    manifest_path: Path,
    run_record_path: Path,
    evidence_dir: Path,
    audit_path: Path,
) -> dict[str, Any]:
    manifest, cases = verify_manifest(manifest_path)
    run_record = _read(run_record_path)
    audit = _read(audit_path)
    cases_by_id = {case["case_id"]: case for case in cases}
    case_ids = set(cases_by_id)
    audited = _audit_cases(audit, case_ids)

    integrity: list[str] = []
    if run_record.get("formal_run") is not True:
        integrity.append("run_record_not_formal")
    if run_record.get("case_count") != len(cases):
        integrity.append("run_record_case_count_mismatch")
    if run_record.get("selected_case_ids") not in ([], None):
        integrity.append("formal_run_contains_case_filter")
    identity = run_record.get("execution_identity")
    if not isinstance(identity, dict):
        identity = {}
        integrity.append("missing_execution_identity")
    if identity.get("clean_tree") is not True:
        integrity.append("clean_tree_not_verified")
    if identity.get("case_file_sha256") != manifest["case_file_sha256"]:
        integrity.append("case_digest_mismatch")
    if identity.get("manifest_sha256") != _digest(manifest_path):
        integrity.append("manifest_digest_mismatch")

    run_cases = run_record.get("cases")
    run_ids = {
        item.get("case_id")
        for item in run_cases or []
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    if run_ids != case_ids:
        integrity.append("run_record_case_set_mismatch")
    if {path.stem for path in evidence_dir.glob("*.json")} != case_ids:
        integrity.append("evidence_file_set_mismatch")

    false_go = 0
    budget_count = 0
    budget_closed = 0
    results: list[dict[str, Any]] = []
    for case_id in sorted(case_ids):
        failures = list(audited[case_id])
        evidence_path = evidence_dir / f"{case_id}.json"
        observed: str | None = None
        if not evidence_path.exists():
            failures.append("missing_case_evidence")
        else:
            evidence = _read(evidence_path)
            if evidence.get("case_id") != case_id:
                failures.append("case_id_mismatch")
            terminal = evidence.get("terminal")
            observed = terminal if isinstance(terminal, str) else None
            if observed is None:
                failures.append("missing_terminal")
            if evidence.get("execution_identity") != identity:
                failures.append("execution_identity_mismatch")
            violations = evidence.get("budget_violations")
            budget_ok = evidence.get("budget_compliance") is True
            if not isinstance(violations, list):
                failures.append("invalid_budget_violations")
                violations = ["invalid"]
            if violations or not budget_ok:
                budget_count += 1
                if observed in {"blocked", "failed"}:
                    budget_closed += 1
                else:
                    failures.append("budget_not_fail_closed")
                failures.append("budget_exhausted")

        allowed = allowed_terminals(cases_by_id[case_id])
        if observed == "succeeded" and "succeeded" not in allowed:
            false_go += 1
            failures.append("false_go")
        if observed not in allowed:
            failures.append("unexpected_terminal")
        failures = sorted(set(failures))
        results.append(
            {
                "case_id": case_id,
                "observed_terminal": observed,
                "allowed_terminals": sorted(allowed),
                "passed": not integrity and not failures,
                "zero_tolerance_failures": failures,
            }
        )

    required = (
        "critical_safety_events",
        "fabricated_identifiers",
        "critical_unsupported_claims",
        "noncritical_unsupported_claim_rate",
        "citation_mismatch_rate",
        "repair_attempts",
        "repair_successes",
    )
    for field in required:
        if field not in audit:
            raise ValueError(f"audit missing {field}")

    return {
        "audit_complete": audit.get("audit_complete") is True and not integrity,
        "run_integrity_failures": integrity,
        "false_go": false_go,
        "critical_safety_events": audit["critical_safety_events"],
        "fabricated_identifiers": audit["fabricated_identifiers"],
        "critical_unsupported_claims": audit["critical_unsupported_claims"],
        "noncritical_unsupported_claim_rate": audit["noncritical_unsupported_claim_rate"],
        "citation_mismatch_rate": audit["citation_mismatch_rate"],
        "repair_attempts": audit["repair_attempts"],
        "repair_successes": audit["repair_successes"],
        "budget_exhaustion_count": budget_count,
        "budget_fail_closed_count": budget_closed,
        "cases": results,
        "provenance": {
            "manifest_sha256": _digest(manifest_path),
            "run_record_sha256": _digest(run_record_path),
            "audit_sha256": _digest(audit_path),
            "case_file_sha256": manifest["case_file_sha256"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-record", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = assemble(
            args.manifest,
            args.run_record,
            args.evidence_dir,
            args.audit,
        )
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0 if result["audit_complete"] else 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L deterministic summary error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
