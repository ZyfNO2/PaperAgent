from __future__ import annotations

import subprocess
import traceback
from pathlib import Path

from evidence_bound_module_prepatch import apply_all
from evidence_bound_module_remaining_patch import apply_remaining

_FAILURE_LOG = Path(".github/evidence-bound-module-followup-failure.log")


def _run(*args: str) -> None:
    subprocess.run(args, check=False)


def _persist_failure(rendered: str) -> None:
    print(rendered)
    _run("git", "reset", "--hard", "HEAD")
    _FAILURE_LOG.write_text(rendered, encoding="utf-8")
    _run("git", "config", "user.name", "github-actions[bot]")
    _run(
        "git",
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    _run("git", "add", str(_FAILURE_LOG))
    _run("git", "commit", "-m", "chore(ci): record module repair failure")
    _run("git", "push", "origin", "HEAD:fix/evidence-bound-module-contracts")


def main() -> None:
    try:
        apply_all()
        apply_remaining()
    except BaseException:
        rendered = traceback.format_exc()
        _persist_failure(rendered)
        raise


if __name__ == "__main__":
    main()
