from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

_ORIGINAL_RUN_PATH = runpy.run_path
_RUFF_TARGETS = (
    "src/paperagent",
    "tests",
    "scripts/score_academic_tailoring_retrieval_v1.py",
)
_TARGETED_TESTS = (
    "tests/methodology/test_method_design_draft.py",
    "tests/evals/test_adapter_module_contract.py",
    "tests/evals/test_academic_tailoring_retrieval_v1_scorer.py",
    "tests/evals/test_claw_benchmark_adapter.py",
)


def _diagnostic(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
    )


def _validation_preflight() -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        check=True,
        text=True,
    )
    subprocess.run(["ruff", "format", *_RUFF_TARGETS], check=True, text=True)
    lint = subprocess.run(
        ["ruff", "check", "--fix", *_RUFF_TARGETS],
        text=True,
        capture_output=True,
    )
    if lint.returncode:
        raise RuntimeError(f"ruff preflight failed:\n{_diagnostic(lint)}")
    tests = subprocess.run(
        ["pytest", "-q", *_TARGETED_TESTS],
        text=True,
        capture_output=True,
    )
    if tests.returncode:
        raise RuntimeError(f"targeted pytest preflight failed:\n{_diagnostic(tests)}")


def _run_path_with_validation(
    path_name: str, *args: object, **kwargs: object
) -> dict[str, object]:
    result = _ORIGINAL_RUN_PATH(path_name, *args, **kwargs)
    if Path(path_name).name.startswith("paperagent-module-patch-"):
        _validation_preflight()
    return result


runpy.run_path = _run_path_with_validation
