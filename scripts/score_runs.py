from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DIMENSION_WEIGHTS = {
    "scientific_decision": 25,
    "evidence_role_binding": 20,
    "baseline_and_comparator_specificity": 15,
    "falsifiable_hypothesis": 15,
    "compatibility_analysis": 10,
    "fair_experiment_design": 10,
    "risk_and_stop_conditions": 5,
}


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be an object")
        rows.append(value)
    return rows


def project_runtime_input(case: dict[str, Any]) -> dict[str, object]:
    """Return the complete and exclusive production-visible payload."""

    raw = case["input"]
    supplied = raw["supplied_materials"]
    return {
        "user_input": raw["user_request"],
        "supplied_material_titles": tuple(item["title"] for item in supplied),
        "user_declared_roles": tuple(item["declared_role"] for item in supplied),
        "declared_constraints": tuple(raw["declared_constraints"]),
    }


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _accepted_reviews(trace: dict[str, Any], role: str) -> list[dict[str, Any]]:
    role_map = {
        "strong_comparator": "strong_comparison",
        "mechanism": "parallel_method",
        "supplied_material": None,
    }
    expected = role_map.get(role, role)
    reviews = []
    for item in trace.get("evidence_reviews", []):
        if not isinstance(item, dict) or not item.get("accepted"):
            continue
        if role == "supplied_material":
            if item.get("source_is_supplied_material"):
                reviews.append(item)
        elif item.get("role") == expected:
            reviews.append(item)
    return reviews


def _hypothesis_complete(trace: dict[str, Any]) -> bool:
    hypothesis = trace.get("hypothesis")
    if not isinstance(hypothesis, dict):
        return False
    fields = ("condition", "limitation", "mechanism", "intervention", "target_metric", "guardrail")
    return all(_present(hypothesis.get(field)) for field in fields)


def _baseline_complete(trace: dict[str, Any]) -> bool:
    baseline = trace.get("baseline")
    if not isinstance(baseline, dict):
        return False
    return bool(
        _present(baseline.get("name"))
        and _present(baseline.get("source_evidence_id"))
        and _present(baseline.get("dataset"))
        and _present(baseline.get("split"))
        and baseline.get("metrics")
        and baseline.get("reproduced") is True
        and _present(baseline.get("reproduced_metric"))
    )


def _strong_comparator_complete(trace: dict[str, Any]) -> bool:
    baseline = trace.get("baseline")
    names = baseline.get("strong_comparisons", []) if isinstance(baseline, dict) else []
    experiments = trace.get("experiments", [])
    has_arm = any(
        isinstance(item, dict)
        and item.get("arm_type") == "strong_comparison"
        and _present(item.get("experiment_id"))
        for item in experiments
    )
    has_review = any(
        item.get("identity_verified") is True
        and item.get("relevance_passed") is True
        for item in _accepted_reviews(trace, "strong_comparator")
    )
    return bool(names and has_arm and has_review)


def _compatibility_complete(trace: dict[str, Any]) -> bool:
    modules = trace.get("modules", [])
    if not modules:
        return False
    return all(
        isinstance(item, dict)
        and item.get("role_compatible") is True
        and _present(item.get("original_role"))
        and _present(item.get("proposed_role"))
        and _present(item.get("input_semantics"))
        and _present(item.get("output_semantics"))
        for item in modules
    )


def _fair_experiment_complete(trace: dict[str, Any]) -> bool:
    experiments = trace.get("experiments", [])
    if not experiments:
        return False
    return all(
        isinstance(item, dict)
        and _present(item.get("experiment_id"))
        and _present(item.get("dataset"))
        and _present(item.get("split"))
        and bool(item.get("metrics"))
        and _present(item.get("stopping_criteria"))
        for item in experiments
    )


def hard_failures(case: dict[str, Any], trace: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    oracle = case["oracle"]
    accepted_decisions = set(oracle["accepted_decisions"])

    if trace.get("future_or_test_leakage"):
        failures.append("runtime_or_production_leakage")
    if trace.get("fabricated_items"):
        failures.append("fabricated_evidence")
    if trace.get("trace_audit_passed") is False:
        failures.append("trace_contract_failure")

    for review in trace.get("evidence_reviews", []):
        if not isinstance(review, dict) or not review.get("accepted") or not review.get("core_evidence"):
            continue
        if review.get("identity_verified") is not True or review.get("relevance_passed") is not True:
            failures.append("unverified_or_irrelevant_core_evidence")
            break

    supplied = [
        item
        for item in trace.get("evidence_reviews", [])
        if isinstance(item, dict) and item.get("source_is_supplied_material") and item.get("accepted")
    ]
    if any(
        item.get("identity_verified") is not True or item.get("role_compatible") is False
        for item in supplied
    ):
        failures.append("forced_incompatible_supplied_material")

    if trace.get("stronger_baselines_considered") and not _strong_comparator_complete(trace):
        failures.append("unsupported_comparator_counted_as_verified")

    if trace.get("pilot_recommended") and oracle.get("pilot_allowed") is not True:
        failures.append("pilot_recommended_when_oracle_disallows_pilot")

    if trace.get("novelty_claimed_from_composition_only"):
        failures.append("composition_only_novelty")

    if trace.get("decision") == "GO" and (not _baseline_complete(trace) or not _hypothesis_complete(trace)):
        failures.append("successful_decision_without_reproducible_baseline_or_hypothesis")

    if trace.get("decision") not in {"GO", "REVISE", "NO_GO"}:
        failures.append("invalid_scientific_decision")
    if not accepted_decisions:
        failures.append("oracle_has_no_accepted_decision")

    return list(dict.fromkeys(failures))


def _role_score(case: dict[str, Any], trace: dict[str, Any]) -> tuple[int, list[str]]:
    requirements = case["oracle"]["evidence_requirements"]
    passed = 0
    findings: list[str] = []
    for requirement in requirements:
        role = requirement["role"]
        if role == "baseline":
            ok = _baseline_complete(trace)
        elif role == "strong_comparator":
            ok = _strong_comparator_complete(trace)
        elif role == "mechanism":
            ok = _hypothesis_complete(trace)
        elif role == "risk":
            ok = bool(trace.get("negative_results_visible") or trace.get("stop_conditions"))
        elif role == "supplied_material":
            reviews = _accepted_reviews(trace, role)
            ok = bool(reviews) and all(
                item.get("identity_verified") is True and item.get("role_compatible") is True
                for item in reviews
            )
        else:
            ok = False
        findings.append(f"{role}:{'pass' if ok else 'missing'}")
        passed += int(ok)
    earned = round(DIMENSION_WEIGHTS["evidence_role_binding"] * passed / max(1, len(requirements)))
    return earned, findings


def score_case(case: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    failures = hard_failures(case, trace)
    decision_ok = trace.get("decision") in set(case["oracle"]["accepted_decisions"])
    role_earned, role_findings = _role_score(case, trace)

    required_roles = {item["role"] for item in case["oracle"]["evidence_requirements"]}
    specificity_checks = []
    if "baseline" in required_roles:
        specificity_checks.append(_baseline_complete(trace))
    if "strong_comparator" in required_roles:
        specificity_checks.append(_strong_comparator_complete(trace))
    specificity = (
        round(15 * sum(specificity_checks) / len(specificity_checks))
        if specificity_checks
        else 15
    )

    hypothesis = 15 if _hypothesis_complete(trace) else 0
    capability = case["metadata"]["capability"]
    compatibility_required = capability in {"interface_compatibility", "evidence_role_binding"}
    compatibility = 10 if (not compatibility_required or _compatibility_complete(trace)) else 0
    fair_experiment = 10 if _fair_experiment_complete(trace) else 0
    risk = 5 if trace.get("negative_results_visible") or trace.get("stop_conditions") else 0

    dimensions = {
        "scientific_decision": 25 if decision_ok else 0,
        "evidence_role_binding": role_earned,
        "baseline_and_comparator_specificity": specificity,
        "falsifiable_hypothesis": hypothesis,
        "compatibility_analysis": compatibility,
        "fair_experiment_design": fair_experiment,
        "risk_and_stop_conditions": risk,
    }
    raw_score = sum(dimensions.values())
    score = 0 if failures else raw_score
    return {
        "case_id": case["case_id"],
        "decision": trace.get("decision"),
        "accepted_decisions": case["oracle"]["accepted_decisions"],
        "decision_matches": decision_ok,
        "pilot_recommended": bool(trace.get("pilot_recommended")),
        "pilot_allowed": bool(case["oracle"]["pilot_allowed"]),
        "hard_failures": failures,
        "dimensions": dimensions,
        "role_findings": role_findings,
        "raw_score": raw_score,
        "score": score,
        "passed": decision_ok and not failures and score >= 80,
    }


def score_dataset(cases: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {trace["case_id"]: trace for trace in traces}
    missing = [case["case_id"] for case in cases if case["case_id"] not in by_id]
    if missing:
        raise ValueError(f"missing run traces: {missing}")
    results = [score_case(case, by_id[case["case_id"]]) for case in cases]
    total = len(results)
    decision_accuracy = sum(item["decision_matches"] for item in results) / total
    hard_failure_count = sum(len(item["hard_failures"]) for item in results)
    average_score = sum(item["score"] for item in results) / total
    report: dict[str, Any] = {
        "schema": "paperagent.academic-holdout.report.v2",
        "split": cases[0]["metadata"]["split"] if cases else None,
        "total": total,
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "decision_accuracy": decision_accuracy,
        "average_score": average_score,
        "hard_failure_count": hard_failure_count,
        "fabricated_evidence_count": sum(
            "fabricated_evidence" in item["hard_failures"] for item in results
        ),
        "unsupported_comparator_count": sum(
            "unsupported_comparator_counted_as_verified" in item["hard_failures"]
            for item in results
        ),
        "cases": results,
    }
    report["report_digest"] = _digest(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Academic Method Holdout v2 traces.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("traces", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = score_dataset(load_jsonl(args.cases), load_jsonl(args.traces))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
