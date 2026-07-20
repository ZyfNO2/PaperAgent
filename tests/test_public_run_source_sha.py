from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_public_dev import resolve_benchmark_source_sha


class PublicRunSourceShaTests(unittest.TestCase):
    def test_explicit_benchmark_sha_wins_over_github_merge_sha(self) -> None:
        benchmark_sha = "a" * 40
        with patch.dict(
            os.environ,
            {
                "PAPERAGENT_BENCHMARK_SHA": benchmark_sha,
                "GITHUB_SHA": "b" * 40,
            },
            clear=False,
        ):
            self.assertEqual(resolve_benchmark_source_sha(), benchmark_sha)

    def test_git_checkout_sha_is_used_when_override_is_absent(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["git", "rev-parse", "HEAD"],
            returncode=0,
            stdout="c" * 40 + "\n",
            stderr="",
        )
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.run_public_dev.subprocess.run",
            return_value=completed,
        ) as run:
            value = resolve_benchmark_source_sha(Path("/tmp/frozen-benchmark"))

        self.assertEqual(value, "c" * 40)
        run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"],
            cwd=Path("/tmp/frozen-benchmark"),
            check=True,
            capture_output=True,
            text=True,
        )

    def test_invalid_explicit_sha_fails_closed(self) -> None:
        with patch.dict(
            os.environ,
            {"PAPERAGENT_BENCHMARK_SHA": "not-a-commit"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "exact 40-character"):
                resolve_benchmark_source_sha()


if __name__ == "__main__":
    unittest.main()
