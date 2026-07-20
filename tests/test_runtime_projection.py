from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.score_runs import hard_failures, load_jsonl, project_runtime_input, score_case

ROOT = Path(__file__).resolve().parents[1]


class RuntimeProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = load_jsonl(ROOT / "data/public-dev-v2.jsonl")[0]

    def test_projection_contains_only_runtime_visible_fields(self) -> None:
        projected = project_runtime_input(self.case)
        self.assertEqual(
            set(projected),
            {
                "user_input",
                "supplied_material_titles",
                "user_declared_roles",
                "declared_constraints",
            },
        )
        self.assertNotIn("case_id", projected)
        self.assertNotIn("oracle", projected)
        self.assertNotIn("metadata", projected)

    def test_scorer_only_mutations_do_not_change_projection(self) -> None:
        original = project_runtime_input(self.case)
        mutated = copy.deepcopy(self.case)
        mutated["case_id"] = "mutated-external-id"
        mutated["oracle"] = {
            "accepted_decisions": ["GO"],
            "required_findings": ["mutated"],
            "forbidden_claims": ["mutated"],
            "evidence_requirements": [
                {"role": "risk", "minimum_contract": ["mutated"]}
            ],
            "pilot_allowed": True,
            "hard_failure_conditions": ["mutated"],
        }
        mutated["metadata"] = {
            "split": "private_holdout",
            "capability": "pilot_gate",
            "domain": "mutated-domain",
            "language": "ja",
            "metamorphic_group": "mutated-group",
        }
        self.assertEqual(project_runtime_input(mutated), original)

    def test_user_visible_mutation_changes_projection(self) -> None:
        mutated = copy.deepcopy(self.case)
        mutated["input"]["declared_constraints"].append("new user constraint")
        self.assertNotEqual(project_runtime_input(mutated), project_runtime_input(self.case))


class StructuredScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = copy.deepcopy(RuntimeProjectionTests.case)
        self.trace = {
            "case_id": self.case["case_id"],
            "decision": "REVISE",
            "future_or_test_leakage": False,
            "fabricated_items": [],
            "trace_audit_passed": True,
            "evidence_reviews": [],
            "stronger_baselines_considered": False,
            "pilot_recommended": False,
            "novelty_claimed_from_composition_only": False,
            "baseline": None,
            "hypothesis": None,
            "modules": [],
            "experiments": [],
            "stop_conditions": [],
            "negative_results_visible": False,
            "scientific_readiness": None,
        }

    def test_disallowed_pilot_is_a_hard_failure(self) -> None:
        self.trace["pilot_recommended"] = True
        self.assertIn(
            "pilot_recommended_when_oracle_disallows_pilot",
            hard_failures(self.case, self.trace),
        )

    def test_unresolved_comparator_cannot_be_counted_as_verified(self) -> None:
        self.trace["stronger_baselines_considered"] = True
        self.assertIn(
            "unsupported_comparator_counted_as_verified",
            hard_failures(self.case, self.trace),
        )

    def test_fabrication_forces_zero_score(self) -> None:
        self.trace["fabricated_items"] = ["invented-evidence"]
        result = score_case(self.case, self.trace)
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])
        self.assertIn("fabricated_evidence", result["hard_failures"])

    def test_decision_is_scored_against_external_oracle(self) -> None:
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
    unittest.main()
