from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.freeze_evaluation import DEFAULT_THRESHOLDS, build_freeze_manifest


class FreezeEvaluationTests(unittest.TestCase):
    def _root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        files = {
            "scripts/run_public_dev.py": "runner\n",
            "scripts/score_runs.py": "scorer\n",
            "scripts/scan_production.py": "scanner\n",
            "docs/BENCHMARK_PROTOCOL.md": "protocol\n",
            "schema/case.schema.json": "{}\n",
            "data/public-dev-v2.jsonl": '{"case_id":"dev"}\n',
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return temporary, root

    def test_manifest_pins_all_evaluation_inputs(self) -> None:
        temporary, root = self._root()
        self.addCleanup(temporary.cleanup)
        manifest = build_freeze_manifest(
            repository_root=root,
            production_source_sha="a" * 40,
            benchmark_source_sha="b" * 40,
            production_digest="c" * 64,
        )

        self.assertEqual(manifest["thresholds"], DEFAULT_THRESHOLDS)
        self.assertEqual(
            manifest["thresholds"],
            {
                "decision_accuracy_minimum": 0.80,
                "hard_failure_count_maximum": 0,
                "fabricated_evidence_count_maximum": 0,
                "unsupported_comparator_count_maximum": 0,
                "adapter_created_pilot_count_maximum": 0,
                "metamorphic_decision_consistency_minimum": 0.85,
                "public_private_score_gap_maximum_percentage_points": 10,
            },
        )
        self.assertEqual(
            set(manifest["file_sha256"]),
            {
                "runner",
                "scorer",
                "production_scanner",
                "protocol",
                "case_schema",
                "public_development_data",
            },
        )
        self.assertEqual(len(manifest["freeze_digest"]), 64)
        self.assertNotIn("oracle", manifest["runtime_boundary"])
        self.assertIn("oracle", manifest["scorer_only_fields"])
        self.assertIn("not generated", manifest["private_holdout_status"])

    def test_manifest_digest_changes_when_scorer_changes(self) -> None:
        temporary, root = self._root()
        self.addCleanup(temporary.cleanup)
        kwargs = {
            "repository_root": root,
            "production_source_sha": "a" * 40,
            "benchmark_source_sha": "b" * 40,
            "production_digest": "c" * 64,
        }
        before = build_freeze_manifest(**kwargs)
        (root / "scripts/score_runs.py").write_text("changed scorer\n", encoding="utf-8")
        after = build_freeze_manifest(**kwargs)
        self.assertNotEqual(before["file_sha256"]["scorer"], after["file_sha256"]["scorer"])
        self.assertNotEqual(before["freeze_digest"], after["freeze_digest"])

    def test_invalid_sha_and_missing_input_fail_closed(self) -> None:
        temporary, root = self._root()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(ValueError, "production_source_sha"):
            build_freeze_manifest(
                repository_root=root,
                production_source_sha="short",
                benchmark_source_sha="b" * 40,
                production_digest="c" * 64,
            )

        (root / "scripts/score_runs.py").unlink()
        with self.assertRaisesRegex(ValueError, "freeze inputs missing"):
            build_freeze_manifest(
                repository_root=root,
                production_source_sha="a" * 40,
                benchmark_source_sha="b" * 40,
                production_digest="c" * 64,
            )

    def test_manifest_is_json_serializable(self) -> None:
        temporary, root = self._root()
        self.addCleanup(temporary.cleanup)
        manifest = build_freeze_manifest(
            repository_root=root,
            production_source_sha="a" * 40,
            benchmark_source_sha="b" * 40,
            production_digest="c" * 64,
        )
        serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
        self.assertIn("paperagent.academic-holdout.freeze.v2", serialized)


if __name__ == "__main__":
    unittest.main()
