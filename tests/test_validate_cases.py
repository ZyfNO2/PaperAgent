from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_cases import ValidationError, load_cases, validate_case, validate_dataset  # noqa: E402


class PublicDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "data" / "public-dev-v2.jsonl"
        cls.cases = load_cases(cls.path)

    def test_public_dataset_passes(self) -> None:
        validate_dataset(self.cases)

    def test_oracle_cannot_be_added_to_runtime_input(self) -> None:
        case = copy.deepcopy(self.cases[0])
        case["input"]["accepted_decisions"] = case["oracle"]["accepted_decisions"]
        with self.assertRaisesRegex(ValidationError, "unexpected input fields"):
            validate_case(case, public=True)

    def test_legacy_domain_term_is_rejected(self) -> None:
        case = copy.deepcopy(self.cases[0])
        case["input"]["user_request"] = "Design a small object detector"
        with self.assertRaisesRegex(ValidationError, "legacy benchmark term"):
            validate_case(case, public=True)

    def test_placeholder_comparator_case_forbids_verified_claim(self) -> None:
        comparator_cases = [
            case
            for case in self.cases
            if case["metadata"]["capability"] == "strong_comparator"
        ]
        self.assertGreaterEqual(len(comparator_cases), 2)
        for case in comparator_cases:
            self.assertIn(
                "strong_comparator_verified", case["oracle"]["forbidden_claims"]
            )
            self.assertFalse(case["oracle"]["pilot_allowed"])

    def test_jsonl_is_canonical_one_object_per_line(self) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(12, len(lines))
        self.assertTrue(all(isinstance(json.loads(line), dict) for line in lines))


if __name__ == "__main__":
    unittest.main()
