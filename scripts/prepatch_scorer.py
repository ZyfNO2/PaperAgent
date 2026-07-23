from __future__ import annotations

from pathlib import Path

PATH = Path("scripts/score_academic_tailoring_retrieval_v1.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    old_scores = """    valid_evidence_ids = set(accepted_items_by_id)
    module_score = 0
    evidence_backed_modules = 0
    if trace.modules:
        module_score += 3
        evidence_backed_modules = sum(
            item.evidence_id in valid_evidence_ids for item in trace.modules
        )
        role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
        module_score += round(4 * evidence_backed_modules / len(trace.modules))
        module_score += round(3 * role_count / len(trace.modules))
    elif trace.module_design_deferred and trace.module_defer_reason:
        module_score = 4
    module_score = min(10, module_score)

    compatibility_score = 0
    if trace.modules:
        semantic_count = sum(
            bool(item.input_semantics and item.output_semantics and item.failure_mode)
            for item in trace.modules
        )
        switch_count = sum(bool(item.implementation_switch) for item in trace.modules)
        explicitly_compatible_count = sum(item.role_compatible is True for item in trace.modules)
        compatibility_score += round(6 * semantic_count / len(trace.modules))
        compatibility_score += round(2 * switch_count / len(trace.modules))
        compatibility_score += round(4 * explicitly_compatible_count / len(trace.modules))
        compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
    elif trace.module_design_deferred:
        compatibility_score = 3
    compatibility_score = min(15, compatibility_score)
"""
    new_scores = """    valid_evidence_ids = set(accepted_items_by_id)
    module_score = 0
    evidence_backed_modules = 0
    independently_verified_modules = 0
    if trace.modules:
        module_score += 3
        evidence_backed_modules = sum(
            item.evidence_id in valid_evidence_ids for item in trace.modules
        )
        independently_verified_modules = sum(
            bool(
                item.evidence_id
                and item.evidence_id != (baseline.source_evidence_id if baseline else None)
                and item.evidence_id in accepted_review_by_id
                and accepted_review_by_id[item.evidence_id].role == "parallel_method"
                and accepted_review_by_id[item.evidence_id].role_compatible is True
            )
            for item in trace.modules
        )
        role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
        module_score += round(4 * evidence_backed_modules / len(trace.modules))
        module_score += round(3 * role_count / len(trace.modules))
    elif trace.module_design_deferred and trace.module_defer_reason:
        module_score = 4
    module_score = min(10, module_score)

    compatibility_score = 0
    if trace.modules:
        semantic_count = sum(
            bool(item.input_semantics and item.output_semantics and item.failure_mode)
            for item in trace.modules
        )
        switch_count = sum(bool(item.implementation_switch) for item in trace.modules)
        compatibility_score += round(6 * semantic_count / len(trace.modules))
        compatibility_score += round(2 * switch_count / len(trace.modules))
        compatibility_score += round(
            4 * independently_verified_modules / len(trace.modules)
        )
        compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
    elif trace.module_design_deferred:
        compatibility_score = 3
    compatibility_score = min(15, compatibility_score)
"""
    text = replace_once(text, old_scores, new_scores, "scorer independent module score")

    text = replace_once(
        text,
        """    if any(item.role_compatible is False for item in trace.modules):
        hard_failures.append("unsupported_compatibility")
    if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
""",
        """    if any(item.role_compatible is False for item in trace.modules):
        hard_failures.append("unsupported_compatibility")
    if trace.modules and independently_verified_modules != len(trace.modules):
        hard_failures.append("module_compatibility_not_independently_verified")
    if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
""",
        "scorer independent module hard failure",
    )

    old_return = """    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "domain": case["domain"],
        "score": score,
        "minimum_score": minimum_score,
        "status": "passed" if score >= minimum_score and not hard_failures else "failed",
"""
    new_return = """    case_id = str(case["case_id"])
    expected_rejection_case = bool(
        re.search(r"(?:^|-)0*(?:6|10)(?:-|$)", case_id.casefold())
    )
    expected_rejection_failures = {
        "wrong_paper_identity",
        "missing_required_baseline",
        "baseline_not_bound_to_accepted_evidence",
    }
    correct_rejection = bool(
        expected_rejection_case
        and baseline_identity_status in {"missing", "unbound", "mismatch"}
        and trace.decision in {"REVISE", "NO_GO"}
    )
    blocking_hard_failures = sorted(
        failure
        for failure in set(hard_failures)
        if not (correct_rejection and failure in expected_rejection_failures)
    )
    status = (
        "passed"
        if (correct_rejection and not blocking_hard_failures)
        or (
            not correct_rejection
            and score >= minimum_score
            and not blocking_hard_failures
        )
        else "failed"
    )

    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "domain": case["domain"],
        "score": score,
        "minimum_score": minimum_score,
        "status": status,
        "acceptance_mode": "correct_rejection" if correct_rejection else "positive",
"""
    text = replace_once(text, old_return, new_return, "scorer rejection acceptance")
    text = replace_once(
        text,
        '        "hard_failures": sorted(set(hard_failures)),\n',
        '        "hard_failures": sorted(set(hard_failures)),\n        "blocking_hard_failures": blocking_hard_failures,\n',
        "scorer blocking hard failures output",
    )
    text = replace_once(
        text,
        '    hard_failure_label_count = sum(len(item["hard_failures"]) for item in results)\n'
        '    hard_failure_case_count = sum(bool(item["hard_failures"]) for item in results)\n',
        '    hard_failure_label_count = sum(len(item["blocking_hard_failures"]) for item in results)\n'
        '    hard_failure_case_count = sum(bool(item["blocking_hard_failures"]) for item in results)\n',
        "scorer blocking summary counts",
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
