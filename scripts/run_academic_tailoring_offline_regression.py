from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "tests/providers/test_runtime.py",
    "tests/nodes/test_method_design_scientific_deferral.py",
    "tests/evals/test_academic_tailoring_retrieval_v1_scorer.py",
    "tests/methodology/test_declared_baseline_repository_fallback.py",
    "tests/methodology/test_method_design_draft.py",
    "tests/evals/test_adapter_module_contract.py",
)


def main() -> int:
    command = [sys.executable, "-m", "pytest", *TARGETS, "-q"]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
