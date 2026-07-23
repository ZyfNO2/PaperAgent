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


def _ruff_preflight() -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "ruff>=0.12,<0.13"],
        check=True,
        text=True,
    )
    subprocess.run(["ruff", "format", *_RUFF_TARGETS], check=True, text=True)
    result = subprocess.run(
        ["ruff", "check", "--fix", *_RUFF_TARGETS],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        diagnostic = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip()
        )
        raise RuntimeError(f"ruff preflight failed:\n{diagnostic}")


def _run_path_with_ruff(path_name: str, *args: object, **kwargs: object) -> dict[str, object]:
    result = _ORIGINAL_RUN_PATH(path_name, *args, **kwargs)
    if Path(path_name).name.startswith("paperagent-module-patch-"):
        _ruff_preflight()
    return result


runpy.run_path = _run_path_with_ruff
