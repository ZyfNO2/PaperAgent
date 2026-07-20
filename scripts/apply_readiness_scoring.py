from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one replacement in {relative}, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "scripts/score_runs.py",
    """def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


""",
    """def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _readiness(trace: dict[str, Any]) -> dict[str, Any] | None:
    value = trace.get("scientific_readiness")
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    if value.get("basis") != "user_declaration":
        return None
    if value.get("independently_verified") is not False:
        return None
    return value


def _declared_readiness_complete(trace: dict[str, Any]) -> bool:
    readiness = _readiness(trace)
    if readiness is None or readiness.get("explicit_evaluation_protocol_invalid") is True:
        return False
    return all(
        readiness.get(field) is True
        for field in (
            "baseline_readiness_confirmed",
            "evaluation_protocol_validated",
            "comparison_readiness_confirmed",
            "module_validation_confirmed",
            "failure_policy_confirmed",
        )
    )


def _declared_protocol_invalid(trace: dict[str, Any]) -> bool:
    readiness = _readiness(trace)
    return bool(
        readiness is not None
        and readiness.get("explicit_evaluation_protocol_invalid") is True
    )


def _declared_failure_policy(trace: dict[str, Any]) -> bool:
    readiness = _readiness(trace)
    return bool(readiness is not None and readiness.get("failure_policy_confirmed") is True)


""",
)

replace_once(
    "scripts/score_runs.py",
    """    if trace.get("trace_audit_passed") is False:
        failures.append("trace_contract_failure")

    for review in trace.get("evidence_reviews", []):
""",
    """    if trace.get("trace_audit_passed") is False:
        failures.append("trace_contract_failure")
    if trace.get("scientific_readiness") is not None and _readiness(trace) is None:
        failures.append("invalid_readiness_provenance")
    if _declared_protocol_invalid(trace) and trace.get("decision") != "NO_GO":
        failures.append("decision_conflicts_with_explicit_invalid_protocol")

    for review in trace.get("evidence_reviews", []):
""",
)
replace_once(
    "scripts/score_runs.py",
    """    if trace.get("decision") == "GO" and (not _baseline_complete(trace) or not _hypothesis_complete(trace)):
        failures.append("successful_decision_without_reproducible_baseline_or_hypothesis")
""",
    """    if (
        trace.get("decision") == "GO"
        and not _declared_readiness_complete(trace)
        and (not _baseline_complete(trace) or not _hypothesis_complete(trace))
    ):
        failures.append("successful_decision_without_reproducible_baseline_or_hypothesis")
""",
)
replace_once(
    "scripts/score_runs.py",
    """        elif role == "risk":
            ok = bool(trace.get("negative_results_visible") or trace.get("stop_conditions"))
""",
    """        elif role == "risk":
            ok = bool(
                trace.get("negative_results_visible")
                or trace.get("stop_conditions")
                or _declared_failure_policy(trace)
            )
""",
)
replace_once(
    "scripts/score_runs.py",
    """    compatibility_required = capability in {"interface_compatibility", "evidence_role_binding"}
    compatibility = 10 if (not compatibility_required or _compatibility_complete(trace)) else 0
    fair_experiment = 10 if _fair_experiment_complete(trace) else 0
    risk = 5 if trace.get("negative_results_visible") or trace.get("stop_conditions") else 0
""",
    """    compatibility_required = capability in {"interface_compatibility", "evidence_role_binding"}
    readiness = _readiness(trace)
    declared_compatibility = bool(
        readiness is not None and readiness.get("module_validation_confirmed") is True
    )
    compatibility = (
        10
        if not compatibility_required
        or _compatibility_complete(trace)
        or declared_compatibility
        else 0
    )
    fair_experiment = (
        10
        if _fair_experiment_complete(trace) or _declared_readiness_complete(trace)
        else 0
    )
    risk = (
        5
        if trace.get("negative_results_visible")
        or trace.get("stop_conditions")
        or _declared_failure_policy(trace)
        else 0
    )
""",
)

replace_once(
    "tests/test_runtime_projection.py",
    """            "negative_results_visible": False,
        }
""",
    """            "negative_results_visible": False,
            "scientific_readiness": None,
        }
""",
)
replace_once(
    "tests/test_runtime_projection.py",
    """    def test_decision_is_scored_against_external_oracle(self) -> None:
        result = score_case(self.case, self.trace)
        self.assertTrue(result["decision_matches"])
        mutated = copy.deepcopy(self.case)
        mutated["oracle"]["accepted_decisions"] = ["NO_GO"]
        changed = score_case(mutated, self.trace)
        self.assertFalse(changed["decision_matches"])
        self.assertEqual(project_runtime_input(mutated), project_runtime_input(self.case))


if __name__ == "__main__":
""",
    """    def test_decision_is_scored_against_external_oracle(self) -> None:
        result = score_case(self.case, self.trace)
        self.assertTrue(result["decision_matches"])
        mutated = copy.deepcopy(self.case)
        mutated["oracle"]["accepted_decisions"] = ["NO_GO"]
        changed = score_case(mutated, self.trace)
        self.assertFalse(changed["decision_matches"])
        self.assertEqual(project_runtime_input(mutated), project_runtime_input(self.case))

    def test_complete_user_declaration_can_support_go_without_fake_evidence(self) -> None:
        self.trace["decision"] = "GO"
        self.trace["scientific_readiness"] = {
            "basis": "user_declaration",
            "independently_verified": False,
            "baseline_readiness_confirmed": True,
            "evaluation_protocol_validated": True,
            "comparison_readiness_confirmed": True,
            "module_validation_confirmed": True,
            "failure_policy_confirmed": True,
            "explicit_evaluation_protocol_invalid": False,
        }
        failures = hard_failures(self.case, self.trace)
        self.assertNotIn(
            "successful_decision_without_reproducible_baseline_or_hypothesis",
            failures,
        )
        self.assertEqual(self.trace["evidence_reviews"], [])

    def test_partial_user_declaration_does_not_support_go(self) -> None:
        self.trace["decision"] = "GO"
        self.trace["scientific_readiness"] = {
            "basis": "user_declaration",
            "independently_verified": False,
            "baseline_readiness_confirmed": True,
            "evaluation_protocol_validated": True,
            "comparison_readiness_confirmed": False,
            "module_validation_confirmed": True,
            "failure_policy_confirmed": True,
            "explicit_evaluation_protocol_invalid": False,
        }
        self.assertIn(
            "successful_decision_without_reproducible_baseline_or_hypothesis",
            hard_failures(self.case, self.trace),
        )

    def test_readiness_claim_cannot_be_marked_independently_verified(self) -> None:
        self.trace["scientific_readiness"] = {
            "basis": "user_declaration",
            "independently_verified": True,
        }
        self.assertIn("invalid_readiness_provenance", hard_failures(self.case, self.trace))

    def test_explicit_invalid_protocol_requires_no_go(self) -> None:
        self.trace["scientific_readiness"] = {
            "basis": "user_declaration",
            "independently_verified": False,
            "explicit_evaluation_protocol_invalid": True,
        }
        self.assertIn(
            "decision_conflicts_with_explicit_invalid_protocol",
            hard_failures(self.case, self.trace),
        )
        self.trace["decision"] = "NO_GO"
        self.assertNotIn(
            "decision_conflicts_with_explicit_invalid_protocol",
            hard_failures(self.case, self.trace),
        )


if __name__ == "__main__":
""",
)

print("structured readiness scoring applied")
