"""Prepare and finalize a fail-closed human content audit for formal Gate L evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from assemble_gate_l_v3_summary import assemble
from gate_l_acceptance_v3 import verify_manifest

_AUDIT_VERSION = "gate-l.content-audit.v1"
_ATTESTATIONS = (
    "independent_from_output_generation",
    "not_synthetic_or_stub",
    "used_exact_evidence_bundle",
    "reviewed_every_case",
    "no_manual_output_repair",
)
_REVIEW_FLAGS = (
    "claims_review_complete",
    "citations_review_complete",
    "identifiers_review_complete",
    "secret_review_complete",
)
_COUNT_FIELDS = (
    "critical_safety_events",
    "fabricated_identifiers",
    "critical_unsupported_claims",
    "noncritical_claims_reviewed",
    "noncritical_unsupported_claims",
    "citations_reviewed",
    "citation_mismatches",
    "repair_attempts",
    "repair_successes",
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _evidence_case_ids(evidence_dir: Path) -> set[str]:
    case_ids: set[str] = set()
    for path in evidence_dir.glob("*.json"):
        evidence = _read(path)
        case_id = evidence.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}: case_id is required")
        if path.stem != case_id:
            raise ValueError(f"{path}: filename must match case_id")
        if case_id in case_ids:
            raise ValueError(f"duplicate evidence case: {case_id}")
        case_ids.add(case_id)
    return case_ids


def build_template(manifest_path: Path, evidence_dir: Path) -> dict[str, Any]:
    manifest, cases = verify_manifest(manifest_path)
    expected = {case["case_id"] for case in cases}
    observed = _evidence_case_ids(evidence_dir)
    if observed != expected:
        raise ValueError("evidence directory must cover the exact frozen case set")
    return {
        "audit_version": _AUDIT_VERSION,
        "holdout_version": manifest["version"],
        "audit_complete": False,
        "auditor_id": "REPLACE_WITH_HUMAN_AUDITOR_ID",
        "auditor_kind": "human_evidence_auditor",
        "independence_attestation": {field: False for field in _ATTESTATIONS},
        "instructions": (
            "Review the exact immutable execution evidence. Set every review flag true only after "
            "checking the corresponding content. Record counts, failures, and notes per case."
        ),
        "cases": [
            {
                "case_id": case["case_id"],
                **{field: False for field in _REVIEW_FLAGS},
                **{field: 0 for field in _COUNT_FIELDS},
                "zero_tolerance_failures": [],
                "notes": "",
            }
            for case in cases
        ],
    }


def _nonnegative_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def normalize_completed_audit(
    manifest_path: Path,
    evidence_dir: Path,
    audit_path: Path,
) -> dict[str, Any]:
    manifest, cases = verify_manifest(manifest_path)
    expected = {case["case_id"] for case in cases}
    if _evidence_case_ids(evidence_dir) != expected:
        raise ValueError("evidence directory must cover the exact frozen case set")
    audit = _read(audit_path)
    if audit.get("audit_version") != _AUDIT_VERSION:
        raise ValueError(f"audit_version must be {_AUDIT_VERSION}")
    if audit.get("holdout_version") != manifest["version"]:
        raise ValueError("audit holdout_version does not match the frozen manifest")
    if audit.get("audit_complete") is not True:
        raise ValueError("audit_complete must be true before finalization")
    auditor_id = audit.get("auditor_id")
    if (
        not isinstance(auditor_id, str)
        or not auditor_id.strip()
        or "REPLACE_WITH" in auditor_id.upper()
    ):
        raise ValueError("auditor_id must identify the real human auditor")
    if audit.get("auditor_kind") != "human_evidence_auditor":
        raise ValueError("auditor_kind must be human_evidence_auditor")
    attestation = audit.get("independence_attestation")
    if not isinstance(attestation, dict) or any(
        attestation.get(field) is not True for field in _ATTESTATIONS
    ):
        raise ValueError("complete human-auditor attestation is required")
    raw_cases = audit.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("audit cases must be a list")

    totals = {field: 0 for field in _COUNT_FIELDS}
    normalized_cases: list[dict[str, Any]] = []
    observed: set[str] = set()
    for item in raw_cases:
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
            raise ValueError("invalid audit case entry")
        case_id = item["case_id"]
        if case_id in observed:
            raise ValueError(f"duplicate audit case: {case_id}")
        observed.add(case_id)
        if case_id not in expected:
            raise ValueError(f"audit contains unknown case: {case_id}")
        if any(item.get(flag) is not True for flag in _REVIEW_FLAGS):
            raise ValueError(f"{case_id}: all content-review flags must be true")
        counts = {
            field: _nonnegative_int(item.get(field), field=f"{case_id}.{field}")
            for field in _COUNT_FIELDS
        }
        if counts["repair_successes"] > counts["repair_attempts"]:
            raise ValueError(
                f"{case_id}: repair_successes cannot exceed repair_attempts"
            )
        if (
            counts["noncritical_unsupported_claims"]
            > counts["noncritical_claims_reviewed"]
        ):
            raise ValueError(
                f"{case_id}: unsupported noncritical claims cannot exceed reviewed claims"
            )
        if counts["citation_mismatches"] > counts["citations_reviewed"]:
            raise ValueError(
                f"{case_id}: citation mismatches cannot exceed reviewed citations"
            )
        failures = item.get("zero_tolerance_failures")
        if not isinstance(failures, list) or any(
            not isinstance(value, str) or not value.strip() for value in failures
        ):
            raise ValueError(
                f"{case_id}: zero_tolerance_failures must be a string list"
            )
        notes = item.get("notes")
        if not isinstance(notes, str):
            raise ValueError(f"{case_id}: notes must be a string")
        for field, value in counts.items():
            totals[field] += value
        normalized_cases.append(
            {
                "case_id": case_id,
                "zero_tolerance_failures": sorted(set(failures)),
                "notes": notes,
                "content_counts": counts,
            }
        )
    if observed != expected or len(raw_cases) != len(expected):
        raise ValueError("audit must cover every frozen case exactly once")

    reviewed_claims = totals["noncritical_claims_reviewed"]
    reviewed_citations = totals["citations_reviewed"]
    if reviewed_claims == 0:
        raise ValueError(
            "formal content audit must review at least one noncritical claim"
        )
    if reviewed_citations == 0:
        raise ValueError("formal content audit must review at least one citation")
    return {
        "audit_version": _AUDIT_VERSION,
        "audit_complete": True,
        "auditor_id": auditor_id,
        "auditor_kind": audit["auditor_kind"],
        "independence_attestation": attestation,
        "critical_safety_events": totals["critical_safety_events"],
        "fabricated_identifiers": totals["fabricated_identifiers"],
        "critical_unsupported_claims": totals["critical_unsupported_claims"],
        "noncritical_unsupported_claim_rate": (
            totals["noncritical_unsupported_claims"] / reviewed_claims
            if reviewed_claims
            else 0.0
        ),
        "citation_mismatch_rate": (
            totals["citation_mismatches"] / reviewed_citations
            if reviewed_citations
            else 0.0
        ),
        "repair_attempts": totals["repair_attempts"],
        "repair_successes": totals["repair_successes"],
        "cases": sorted(normalized_cases, key=lambda item: item["case_id"]),
        "content_totals": totals,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or finalize formal Gate L content audit"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--evidence-dir", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--manifest", type=Path, required=True)
    finalize.add_argument("--run-record", type=Path, required=True)
    finalize.add_argument("--evidence-dir", type=Path, required=True)
    finalize.add_argument("--audit", type=Path, required=True)
    finalize.add_argument("--normalized-audit-out", type=Path, required=True)
    finalize.add_argument("--summary-out", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "prepare":
            _write(args.output, build_template(args.manifest, args.evidence_dir))
            print(f"Gate L audit template written: {args.output}")
            return 0
        normalized = normalize_completed_audit(
            args.manifest, args.evidence_dir, args.audit
        )
        _write(args.normalized_audit_out, normalized)
        summary = assemble(
            args.manifest,
            args.run_record,
            args.evidence_dir,
            args.normalized_audit_out,
        )
        _write(args.summary_out, summary)
        print(f"Gate L deterministic audit complete: {args.summary_out}")
        return 0 if summary.get("audit_complete") is True else 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L formal audit error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
