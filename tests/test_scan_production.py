from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.scan_production import scan_production


class ProductionScanTests(unittest.TestCase):
    def _production_tree(self, signature: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        path = root / "src/paperagent/claw_benchmark_runtime.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from __future__ import annotations\n\n"
            f"async def execute_benchmark_input({signature}):\n"
            "    return benchmark_input\n",
            encoding="utf-8",
        )
        normalizer = root / "src/paperagent/claw_benchmark_normalizer.py"
        normalizer.write_text(
            "def normalize_paperagent_state(state, context):\n"
            "    outcome = state.get('final_outcome')\n"
            "    pilot_recommended = bool(outcome is not None and outcome.pilot_recommended)\n"
            "    trace = legacy(state, context)\n"
            "    return trace.model_copy(update={'pilot_recommended': pilot_recommended})\n",
            encoding="utf-8",
        )
        return temporary, root

    def test_clean_input_only_signature_passes(self) -> None:
        temporary, root = self._production_tree(
            "*, benchmark_input, llm, search, max_llm_calls, task_id"
        )
        self.addCleanup(temporary.cleanup)

        report = scan_production(root)
        self.assertTrue(report["passed"])
        self.assertEqual(report["private_ngram_count"], 0)
        self.assertEqual(report["scanned_file_count"], 2)
        self.assertTrue(report["pilot_recommendation_source_verified"])

    def test_scorer_field_in_runtime_signature_fails(self) -> None:
        temporary, root = self._production_tree(
            "*, benchmark_input, case_id, oracle, llm, search, max_llm_calls, task_id"
        )
        self.addCleanup(temporary.cleanup)

        report = scan_production(root)
        self.assertFalse(report["passed"])
        finding = report["findings"][0]
        self.assertEqual(finding["code"], "SCORER_FIELD_IN_RUNTIME_SIGNATURE")
        self.assertEqual(finding["parameters"], ["case_id", "oracle"])

    def test_private_ngram_is_reported_by_digest_not_plaintext(self) -> None:
        temporary, root = self._production_tree(
            "*, benchmark_input, llm, search, max_llm_calls, task_id"
        )
        self.addCleanup(temporary.cleanup)
        (root / "tests").mkdir()
        (root / "tests/example.txt").write_text("sealed phrase appears here", encoding="utf-8")
        manifest = root / "private-manifest.json"
        manifest.write_text(
            json.dumps({"forbidden_ngrams": ["sealed phrase"]}),
            encoding="utf-8",
        )

        report = scan_production(root, private_manifest=manifest)
        self.assertFalse(report["passed"])
        findings = [
            item
            for item in report["findings"]
            if item["code"] == "PRIVATE_NGRAM_IN_EVALUATED_REPOSITORY"
        ]
        self.assertEqual(len(findings), 1)
        self.assertNotIn("sealed phrase", json.dumps(findings))
        self.assertEqual(report["private_ngram_count"], 1)

    def test_pilot_value_not_sourced_from_final_outcome_fails(self) -> None:
        temporary, root = self._production_tree(
            "*, benchmark_input, llm, search, max_llm_calls, task_id"
        )
        self.addCleanup(temporary.cleanup)
        normalizer = root / "src/paperagent/claw_benchmark_normalizer.py"
        normalizer.write_text(
            "def normalize_paperagent_state(state, context):\n"
            "    pilot_recommended = True\n"
            "    trace = legacy(state, context)\n"
            "    return trace.model_copy(update={'pilot_recommended': pilot_recommended})\n",
            encoding="utf-8",
        )

        report = scan_production(root)

        self.assertFalse(report["passed"])
        self.assertFalse(report["pilot_recommendation_source_verified"])
        findings = [
            item
            for item in report["findings"]
            if item["code"] == "PILOT_RECOMMENDATION_SOURCE_UNVERIFIED"
        ]
        self.assertEqual(len(findings), 1)

    def test_missing_executor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = scan_production(Path(directory))
        self.assertFalse(report["passed"])
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("RUNTIME_FILE_MISSING", codes)
        self.assertIn("PILOT_NORMALIZER_FILE_MISSING", codes)
        self.assertFalse(report["pilot_recommendation_source_verified"])


if __name__ == "__main__":
    unittest.main()
