from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path

_previous_hook = sys.excepthook


def _run(*args: str) -> None:
    subprocess.run(args, check=False)


def _persist_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: object,
) -> None:
    rendered = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(rendered, file=sys.stderr)
    _run("git", "reset", "--hard", "HEAD")
    Path(".github/evidence-bound-module-followup-failure.log").write_text(
        rendered,
        encoding="utf-8",
    )
    _run("git", "config", "user.name", "github-actions[bot]")
    _run(
        "git",
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    _run("git", "add", ".github/evidence-bound-module-followup-failure.log")
    _run("git", "commit", "-m", "chore(ci): record module follow-up patch failure")
    _run("git", "push", "origin", "HEAD:fix/evidence-bound-module-contracts")
    _previous_hook(exc_type, exc_value, exc_traceback)


sys.excepthook = _persist_exception
