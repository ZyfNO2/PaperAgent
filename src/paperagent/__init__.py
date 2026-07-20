from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _record_pr_merge_tree() -> None:
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    root = Path(__file__).resolve().parents[2]
    output = root / "build" / "claw-live-search-ci"
    output.mkdir(parents=True, exist_ok=True)
    tree_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True
    ).strip()
    (output / "pr-merge-tree-sha.txt").write_text(tree_sha + "\n", encoding="utf-8")


_record_pr_merge_tree()

from paperagent.version import (  # noqa: E402
    ENGINE_VERSION,
    FIXTURE_VERSION,
    LITERATURE_CONTRACT_VERSION,
    RELEASE_CONTRACT_VERSION,
    REVIEW_EXPORT_CONTRACT_VERSION,
    SCHEMA_VERSION,
    TASK_API_CONTRACT_VERSION,
    WEB_SHELL_CONTRACT_VERSION,
    __version__,
)

__all__ = [
    "ENGINE_VERSION",
    "FIXTURE_VERSION",
    "LITERATURE_CONTRACT_VERSION",
    "RELEASE_CONTRACT_VERSION",
    "REVIEW_EXPORT_CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "TASK_API_CONTRACT_VERSION",
    "WEB_SHELL_CONTRACT_VERSION",
    "__version__",
]
