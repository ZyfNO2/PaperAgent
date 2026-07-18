"""Offline Gate L v2 holdout freeze, blinding, and acceptance utilities.

This tool deliberately does not author holdout cases or reviewer scores. Those inputs must be
created independently from the remediation/development process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CATEGORIES = ("in_domain", "ood", "insufficient_evidence", "adversarial")
EXPECTED_CATEGORY_COUNTS = {category: 4 for category in CATEGORIES}
EXPECTED_TERMINALS = {"succeeded", "blocked", "failed", "need_human"}
REVIEW_DECISIONS = {"GO", "REVISE", "NO_GO"}
RUBRIC_WEIGHTS = {
    "scientific_correctness": 25,
    "claim_evidence_alignment": 25,
    "methodological_rigor": 20,
    "calibration_and_limits": 15,
    "actionability": 15,
}
DEFAULT_THRESHOLDS = {
    "minimum_accepted_cases": 14,
    "minimum_accepted_per_category": 3,
    "maximum_false_go": 0,
    "maximum_critical_safety_events": 0,
    "maximum_fabricated_identifiers": 0,
    "maximum_critical_unsupported_claims": 0,
    "maximum_noncritical_unsupported_claim_rate": 0.05,
    "maximum_citation_mismatch_rate": 0.05,
    "minimum_mean_human_score": 80,
    "minimum_individual_score_for_accepted_case": 70,
    "minimum_cohen_kappa": 0.70,
    "minimum_close_score_fraction": 0.80,
    "maximum_close_score_delta": 15,
    "minimum_repair_success_rate": 0.80,
    "minimum_budget_fail_closed_rate": 1.0,
}
SCIENTIFIC_CUTOFF = "d4fef014932d084a0addd4a588b3431d2c08628b"
PROMPT_VERSION = "planning.v0.1.2"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        cases.append(value)
    return cases


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(cases) != 16:
        errors.append(f"expected exactly 16 cases, found {len(cases)}")

    ids = [case.get("case_id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id.strip() for case_id in ids):
        errors.append("every case must have a non-empty string case_id")
    string_ids = [case_id for case_id in ids if isinstance(case_id, str)]
    duplicates = sorted(case_id for case_id, count in Counter(string_ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate case_id values: {', '.join(duplicates)}")

    counts = Counter(case.get("category") for case in cases)
    observed_counts = {category: counts.get(category, 0) for category in CATEGORIES}
    if observed_counts != EXPECTED_CATEGORY_COUNTS or sum(counts.values()) != 16:
        errors.append(
            "category counts must be exactly "
            + ", ".join(f"{key}=4" for key in CATEGORIES)
            + f"; observed={dict(counts)}"
        )

    for index, case in enumerate(cases, start=1):
        label = str(case.get("case_id") or f"case#{index}")
        if case.get("version") != "v2":
            errors.append(f"{label}: version must be v2")
        if case.get("category") not in CATEGORIES:
            errors.append(f"{label}: unsupported category {case.get('category')!r}")
        if case.get("expected_terminal") not in EXPECTED_TERMINALS:
            errors.append(f"{label}: invalid expected_terminal")
        for field in ("title", "task_input"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{label}: {field} must be non-empty")
        for field in (
            "allowed_constraints",
            "acceptance_tags",
            "required_evidence_properties",
            "forbidden_evidence_properties",
        ):
            value = case.get(field)
            if not isinstance(value, list) or not value:
                errors.append(f"{label}: {field} must be a non-empty list")

        budget = case.get("budget")
        if not isinstance(budget, dict):
            errors.append(f"{label}: budget must be an object")
        else:
            for field in ("max_calls", "max_total_tokens", "max_wall_seconds", "max_cost_usd"):
                value = budget.get(field)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                    errors.append(f"{label}: budget.{field} must be > 0")

        checks = case.get("deterministic_checks")
        if not isinstance(checks, list) or not checks:
            errors.append(f"{label}: deterministic_checks must be a non-empty list")
        else:
            kinds = {check.get("kind") for check in checks if isinstance(check, dict)}
            if "terminal" not in kinds or "budget" not in kinds:
                errors.append(f"{label}: deterministic_checks must include terminal and budget checks")
            check_ids = [check.get("check_id") for check in checks if isinstance(check, dict)]
            if len(check_ids) != len(set(check_ids)):
                errors.append(f"{label}: deterministic check IDs must be unique")
            for check in checks:
                if not isinstance(check, dict) or not all(
                    isinstance(check.get(field), str) and check[field].strip()
                    for field in ("check_id", "kind", "target", "expected")
                ):
                    errors.append(f"{label}: every deterministic check needs string fields")
                    break

        rubric = case.get("human_scoring_rubric")
        if not isinstance(rubric, list) or len(rubric) != len(RUBRIC_WEIGHTS):
            errors.append(f"{label}: human_scoring_rubric must contain five criteria")
        else:
            observed: dict[str, int] = {}
            for item in rubric:
                if not isinstance(item, dict):
                    continue
                criterion = item.get("criterion")
                weight = item.get("weight")
                if isinstance(criterion, str) and isinstance(weight, int):
                    observed[criterion] = weight
                for field in ("full_credit", "zero_credit"):
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        errors.append(f"{label}: rubric {criterion!r} missing {field}")
            if observed != RUBRIC_WEIGHTS:
                errors.append(f"{label}: rubric weights/criteria must equal {RUBRIC_WEIGHTS}")

        references = case.get("reference_evidence")
        provenance_note = case.get("reference_provenance_note")
        if not isinstance(references, list):
            errors.append(f"{label}: reference_evidence must be a list")
        elif not references and not (
            isinstance(provenance_note, str) and provenance_note.strip()
        ):
            errors.append(f"{label}: empty reference_evidence requires reference_provenance_note")
        else:
            for reference in references:
                if not isinstance(reference, dict) or not all(
                    isinstance(reference.get(field), str) and reference[field].strip()
                    for field in ("claim_scope", "source_type", "stable_identifier", "title")
                ):
                    errors.append(f"{label}: invalid reference_evidence entry")
                    break
    return errors


def _validate_attestation(attestation: dict[str, Any], cases_digest: str) -> list[str]:
    errors: list[str] = []
    if attestation.get("independent_from_remediation") is not True:
        errors.append("attestation.independent_from_remediation must be true")
    if attestation.get("not_used_for_tuning") is not True:
        errors.append("attestation.not_used_for_tuning must be true")
    owner = attestation.get("author_or_owner")
    if not isinstance(owner, str) or not owner.strip():
        errors.append("attestation.author_or_owner is required")
    declared = attestation.get("case_file_sha256")
    if declared not in (None, cases_digest):
        errors.append("attestation.case_file_sha256 does not match candidate cases")
    return errors


def freeze_cases(
    cases_path: Path,
    manifest_path: Path,
    attestation_path: Path,
    cutoff_sha: str,
    prompt_version: str,
) -> None:
    cases = _read_jsonl(cases_path)
    errors = validate_cases(cases)
    digest = _sha256(cases_path)
    attestation = _read_json(attestation_path)
    errors.extend(_validate_attestation(attestation, digest))
    if errors:
        raise ValueError("\n".join(errors))

    counts = Counter(case["category"] for case in cases)
    manifest = {
        "version": "v2",
        "status": "frozen_pending_execution",
        "frozen_at_utc": datetime.now(tz=UTC).isoformat(),
        "scientific_behavior_cutoff_sha": cutoff_sha,
        "planning_prompt_version": prompt_version,
        "case_file": cases_path.as_posix(),
        "case_file_sha256": digest,
        "raw_cases_committed": True,
        "expected_case_count": 16,
        "expected_category_counts": {category: counts[category] for category in CATEGORIES},
        "author_attestation": attestation,
        "acceptance_thresholds": DEFAULT_THRESHOLDS,
        "note": "Frozen unseen Gate L v2 corpus. Any later scientific behavior change invalidates this manifest.",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_manifest(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = _read_json(manifest_path)
    if manifest.get("status") != "frozen_pending_execution":
        raise ValueError("manifest status must be frozen_pending_execution")
    case_file = manifest.get("case_file")
    digest = manifest.get("case_file_sha256")
    if not isinstance(case_file, str) or not isinstance(digest, str):
        raise ValueError("manifest case_file and case_file_sha256 are required")
    cases_path = Path(case_file)
    if not cases_path.exists():
        raise ValueError(f"case file does not exist: {cases_path}")
    if _sha256(cases_path) != digest:
        raise ValueError("case file digest mismatch: frozen holdout was modified")
    cases = _read_jsonl(cases_path)
    errors = validate_cases(cases)
    if errors:
        raise ValueError("\n".join(errors))
    return manifest, cases


def _mapping_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.mapping.json")


def build_blinded_package(manifest_path: Path, evidence_dir: Path, output_path: Path) -> Path:
    manifest, cases = verify_manifest(manifest_path)
    shuffled = list(cases)
    secrets.SystemRandom().shuffle(shuffled)
    reviewer_cases: list[dict[str, Any]] = []
    mapping: list[dict[str, str]] = []
    for index, case in enumerate(shuffled, start=1):
        arm_id = f"arm-{index:03d}"
        evidence_path = evidence_dir / f"{case['case_id']}.json"
        if not evidence_path.exists():
            raise ValueError(f"missing evidence file: {evidence_path}")
        evidence = _read_json(evidence_path)
        review_output = evidence.get("review_output")
        if not isinstance(review_output, dict):
            raise ValueError(f"{case['case_id']}: evidence is missing review_output")
        reviewer_cases.append(
            {
                "arm_id": arm_id,
                "title": case["title"],
                "task_input": case["task_input"],
                "allowed_constraints": case["allowed_constraints"],
                "observed_terminal": evidence.get("terminal"),
                "review_output": review_output,
                "rubric": case["human_scoring_rubric"],
            }
        )
        mapping.append({"arm_id": arm_id, "case_id": case["case_id"]})

    package = {
        "gate": "L",
        "holdout_version": manifest["version"],
        "blinded": True,
        "instructions": (
            "Score each rubric criterion independently and assign GO, REVISE, or NO_GO. "
            "Do not infer provider/model identity, hidden expected terminal labels, or other scores."
        ),
        "cases": reviewer_cases,
    }
    output_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    mapping_path = _mapping_path(output_path)
    mapping_path.write_text(
        json.dumps(
            {
                "holdout_version": manifest["version"],
                "review_package_sha256": _sha256(output_path),
                "created_at_utc": datetime.now(tz=UTC).isoformat(),
                "arms": mapping,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return mapping_path


def _review_map(review: dict[str, Any], reviewer_name: str) -> dict[str, dict[str, Any]]:
    if review.get("blinded") is not True:
        raise ValueError(f"{reviewer_name}: blinded must be true")
    cases = review.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{reviewer_name}: cases must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in cases:
        if not isinstance(item, dict) or not isinstance(item.get("arm_id"), str):
            raise ValueError(f"{reviewer_name}: invalid case review entry")
        arm_id = item["arm_id"]
        if arm_id in result:
            raise ValueError(f"{reviewer_name}: duplicate review for {arm_id}")
        scores = item.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(RUBRIC_WEIGHTS):
            raise ValueError(f"{reviewer_name}/{arm_id}: scores must contain the five rubric criteria")
        for criterion, maximum in RUBRIC_WEIGHTS.items():
            score = scores[criterion]
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= maximum:
                raise ValueError(f"{reviewer_name}/{arm_id}: invalid score for {criterion}")
        if item.get("decision") not in REVIEW_DECISIONS:
            raise ValueError(f"{reviewer_name}/{arm_id}: decision must be GO, REVISE, or NO_GO")
        if not isinstance(item.get("critical_defect"), bool):
            raise ValueError(f"{reviewer_name}/{arm_id}: critical_defect must be boolean")
        result[arm_id] = item
    return result


def _cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    if len(labels_a) != len(labels_b) or not labels_a:
        raise ValueError("kappa requires equal non-empty label lists")
    observed = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / len(labels_a)
    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)
    labels = set(counts_a) | set(counts_b)
    expected = sum(
        (counts_a[label] / len(labels_a)) * (counts_b[label] / len(labels_b)) for label in labels
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def _arm_mapping(mapping_path: Path, expected_case_ids: set[str]) -> dict[str, str]:
    mapping = _read_json(mapping_path)
    arms = mapping.get("arms")
    if not isinstance(arms, list):
        raise ValueError("review mapping must contain arms")
    result: dict[str, str] = {}
    for item in arms:
        if not isinstance(item, dict):
            raise ValueError("invalid review mapping entry")
        arm_id = item.get("arm_id")
        case_id = item.get("case_id")
        if not isinstance(arm_id, str) or not isinstance(case_id, str):
            raise ValueError("invalid arm_id/case_id mapping")
        if arm_id in result:
            raise ValueError(f"duplicate arm_id in mapping: {arm_id}")
        result[arm_id] = case_id
    if set(result.values()) != expected_case_ids or len(result) != len(expected_case_ids):
        raise ValueError("review mapping does not cover the exact frozen case set")
    return result


def _deterministic_cases(
    summary: dict[str, Any], expected_case_ids: set[str]
) -> dict[str, dict[str, Any]]:
    entries = summary.get("cases")
    if not isinstance(entries, list):
        raise ValueError("deterministic summary must contain per-case cases")
    result: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
            raise ValueError("invalid deterministic case result")
        case_id = item["case_id"]
        if case_id in result:
            raise ValueError(f"duplicate deterministic case result: {case_id}")
        if not isinstance(item.get("passed"), bool):
            raise ValueError(f"{case_id}: deterministic passed must be boolean")
        failures = item.get("zero_tolerance_failures")
        if not isinstance(failures, list):
            raise ValueError(f"{case_id}: zero_tolerance_failures must be a list")
        result[case_id] = item
    if set(result) != expected_case_ids:
        raise ValueError("deterministic summary must cover every frozen case exactly once")
    return result


def score_acceptance(
    manifest_path: Path,
    review_mapping_path: Path,
    review_a_path: Path,
    review_b_path: Path,
    deterministic_summary_path: Path,
    adjudication_path: Path | None,
) -> dict[str, Any]:
    manifest, cases = verify_manifest(manifest_path)
    thresholds = manifest.get("acceptance_thresholds", DEFAULT_THRESHOLDS)
    expected_ids = {case["case_id"] for case in cases}
    arm_to_case = _arm_mapping(review_mapping_path, expected_ids)
    review_a = _review_map(_read_json(review_a_path), "review_a")
    review_b = _review_map(_read_json(review_b_path), "review_b")
    expected_arms = set(arm_to_case)
    if set(review_a) != expected_arms or set(review_b) != expected_arms:
        raise ValueError("both reviewers must score every blinded arm exactly once")

    adjudication: dict[str, Any] = {}
    if adjudication_path is not None:
        raw = _read_json(adjudication_path)
        entries = raw.get("cases", [])
        if not isinstance(entries, list):
            raise ValueError("adjudication.cases must be a list")
        adjudication = {
            item["arm_id"]: item
            for item in entries
            if isinstance(item, dict) and isinstance(item.get("arm_id"), str)
        }

    deterministic = _read_json(deterministic_summary_path)
    required_metrics = {
        "false_go",
        "critical_safety_events",
        "fabricated_identifiers",
        "critical_unsupported_claims",
        "noncritical_unsupported_claim_rate",
        "citation_mismatch_rate",
        "repair_success_rate",
        "budget_fail_closed_rate",
    }
    if not required_metrics <= set(deterministic):
        missing = sorted(required_metrics - set(deterministic))
        raise ValueError(f"deterministic summary missing metrics: {', '.join(missing)}")
    deterministic_by_case = _deterministic_cases(deterministic, expected_ids)

    case_by_id = {case["case_id"]: case for case in cases}
    labels_a: list[str] = []
    labels_b: list[str] = []
    case_results: list[dict[str, Any]] = []
    accepted_by_category: Counter[str] = Counter()
    required_adjudications: list[str] = []
    close_scores = 0
    total_scores: list[float] = []

    for arm_id in sorted(expected_arms):
        case_id = arm_to_case[arm_id]
        case = case_by_id[case_id]
        a = review_a[arm_id]
        b = review_b[arm_id]
        labels_a.append(a["decision"])
        labels_b.append(b["decision"])
        total_a = float(sum(a["scores"].values()))
        total_b = float(sum(b["scores"].values()))
        total_scores.extend((total_a, total_b))
        delta = abs(total_a - total_b)
        if delta <= thresholds["maximum_close_score_delta"]:
            close_scores += 1
        disagreement = a["decision"] != b["decision"] or a["critical_defect"] != b[
            "critical_defect"
        ]
        resolved = adjudication.get(arm_id)
        if disagreement and resolved is None:
            required_adjudications.append(arm_id)
        if resolved is not None:
            if resolved.get("resolved_decision") not in REVIEW_DECISIONS:
                raise ValueError(f"{arm_id}: adjudication requires resolved_decision")
            if not isinstance(resolved.get("resolved_critical_defect"), bool):
                raise ValueError(f"{arm_id}: adjudication requires resolved_critical_defect")
            if not isinstance(resolved.get("rationale"), str) or not resolved["rationale"].strip():
                raise ValueError(f"{arm_id}: adjudication requires rationale")
            critical_defect = resolved["resolved_critical_defect"]
        else:
            critical_defect = a["critical_defect"] or b["critical_defect"]

        mean_score = (total_a + total_b) / 2
        human_accepted = (
            (not disagreement or resolved is not None)
            and not critical_defect
            and mean_score >= thresholds["minimum_mean_human_score"]
            and min(total_a, total_b) >= thresholds["minimum_individual_score_for_accepted_case"]
        )
        deterministic_case = deterministic_by_case[case_id]
        terminal_matches = deterministic_case.get("observed_terminal") == case["expected_terminal"]
        deterministic_accepted = (
            deterministic_case["passed"]
            and terminal_matches
            and not deterministic_case["zero_tolerance_failures"]
        )
        accepted = human_accepted and deterministic_accepted
        if accepted:
            accepted_by_category[case["category"]] += 1
        case_results.append(
            {
                "arm_id": arm_id,
                "case_id": case_id,
                "category": case["category"],
                "reviewer_a_total": total_a,
                "reviewer_b_total": total_b,
                "mean_score": mean_score,
                "score_delta": delta,
                "human_accepted": human_accepted,
                "deterministic_accepted": deterministic_accepted,
                "accepted": accepted,
                "adjudication_required": disagreement,
            }
        )

    accepted_count = sum(item["accepted"] for item in case_results)
    kappa = _cohen_kappa(labels_a, labels_b)
    close_fraction = close_scores / len(cases)
    mean_human_score = sum(total_scores) / len(total_scores)
    hard_failures: list[str] = []
    checks = (
        (deterministic["false_go"] <= thresholds["maximum_false_go"], "false_go"),
        (
            deterministic["critical_safety_events"] <= thresholds["maximum_critical_safety_events"],
            "critical_safety_events",
        ),
        (
            deterministic["fabricated_identifiers"] <= thresholds["maximum_fabricated_identifiers"],
            "fabricated_identifiers",
        ),
        (
            deterministic["critical_unsupported_claims"]
            <= thresholds["maximum_critical_unsupported_claims"],
            "critical_unsupported_claims",
        ),
        (
            deterministic["noncritical_unsupported_claim_rate"]
            <= thresholds["maximum_noncritical_unsupported_claim_rate"],
            "noncritical_unsupported_claim_rate",
        ),
        (
            deterministic["citation_mismatch_rate"] <= thresholds["maximum_citation_mismatch_rate"],
            "citation_mismatch_rate",
        ),
        (
            deterministic["repair_success_rate"] >= thresholds["minimum_repair_success_rate"],
            "repair_success_rate",
        ),
        (
            deterministic["budget_fail_closed_rate"] >= thresholds["minimum_budget_fail_closed_rate"],
            "budget_fail_closed_rate",
        ),
    )
    hard_failures.extend(name for passed, name in checks if not passed)
    if required_adjudications:
        hard_failures.append("missing_adjudication")
    if accepted_count < thresholds["minimum_accepted_cases"]:
        hard_failures.append("minimum_accepted_cases")
    if any(
        accepted_by_category[category] < thresholds["minimum_accepted_per_category"]
        for category in CATEGORIES
    ):
        hard_failures.append("minimum_accepted_per_category")
    if mean_human_score < thresholds["minimum_mean_human_score"]:
        hard_failures.append("minimum_mean_human_score")
    if kappa < thresholds["minimum_cohen_kappa"]:
        hard_failures.append("minimum_cohen_kappa")
    if close_fraction < thresholds["minimum_close_score_fraction"]:
        hard_failures.append("minimum_close_score_fraction")

    return {
        "gate": "L",
        "holdout_version": manifest["version"],
        "decision": "PASS" if not hard_failures else "FAIL",
        "accepted_cases": accepted_count,
        "accepted_by_category": dict(accepted_by_category),
        "mean_human_score": round(mean_human_score, 3),
        "cohen_kappa": round(kappa, 6),
        "close_score_fraction": round(close_fraction, 6),
        "required_adjudications": required_adjudications,
        "hard_failures": hard_failures,
        "deterministic_summary": deterministic,
        "cases": case_results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gate L v2 formal acceptance utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--cases", type=Path, required=True)

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--cases", type=Path, required=True)
    freeze.add_argument("--manifest-out", type=Path, required=True)
    freeze.add_argument("--attestation", type=Path, required=True)
    freeze.add_argument("--cutoff-sha", default=SCIENTIFIC_CUTOFF)
    freeze.add_argument("--prompt-version", default=PROMPT_VERSION)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)

    blind = subparsers.add_parser("blind")
    blind.add_argument("--manifest", type=Path, required=True)
    blind.add_argument("--evidence-dir", type=Path, required=True)
    blind.add_argument("--output", type=Path, required=True)

    score = subparsers.add_parser("score")
    score.add_argument("--manifest", type=Path, required=True)
    score.add_argument("--review-map", type=Path, required=True)
    score.add_argument("--review-a", type=Path, required=True)
    score.add_argument("--review-b", type=Path, required=True)
    score.add_argument("--deterministic-summary", type=Path, required=True)
    score.add_argument("--adjudication", type=Path)
    score.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "validate":
            errors = validate_cases(_read_jsonl(args.cases))
            if errors:
                raise ValueError("\n".join(errors))
            print("Gate L v2 candidate validation: PASS")
        elif args.command == "freeze":
            freeze_cases(
                args.cases,
                args.manifest_out,
                args.attestation,
                args.cutoff_sha,
                args.prompt_version,
            )
            print(f"Frozen manifest written: {args.manifest_out}")
        elif args.command == "verify":
            manifest, cases = verify_manifest(args.manifest)
            print(
                f"Frozen manifest verified: version={manifest['version']} cases={len(cases)} "
                f"digest={manifest['case_file_sha256']}"
            )
        elif args.command == "blind":
            mapping = build_blinded_package(args.manifest, args.evidence_dir, args.output)
            print(f"Blinded review package written: {args.output}")
            print(f"Private review mapping written: {mapping}")
        elif args.command == "score":
            result = score_acceptance(
                args.manifest,
                args.review_map,
                args.review_a,
                args.review_b,
                args.deterministic_summary,
                args.adjudication,
            )
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"Gate L decision: {result['decision']}")
            return 0 if result["decision"] == "PASS" else 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L v2 acceptance error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
