from __future__ import annotations

import os
import stat
import subprocess
import traceback
from pathlib import Path

from evidence_bound_module_lint_patch import apply_lint_repairs
from evidence_bound_module_prepatch import apply_all
from evidence_bound_module_remaining_patch import apply_remaining
from evidence_bound_module_test_patch import apply_test_repairs

_FAILURE_LOG = Path(".github/evidence-bound-module-followup-failure.log")
_WRAPPER_DIR = Path("/tmp/paperagent-ci-wrappers")
_FIX_BRANCH = os.environ.get("PAPERAGENT_FIX_BRANCH", "automation/evidence-bound-module-finalize")


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
    _run("git", "push", "origin", f"HEAD:{_FIX_BRANCH}")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_ci_wrappers() -> None:
    github_path = os.environ.get("GITHUB_PATH")
    if not github_path:
        return
    _WRAPPER_DIR.mkdir(parents=True, exist_ok=True)
    helper = r'''persist_failure() {
  local source_log="$1"
  local target_log="$2"
  local message="$3"
  git reset --hard HEAD
  cp "$source_log" "$target_log"
  git config user.name 'github-actions[bot]'
  git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  git add "$target_log"
  git commit -m "$message"
  git push origin "HEAD:${PAPERAGENT_FIX_BRANCH}"
}
'''
    _write_executable(
        _WRAPPER_DIR / "ruff",
        "#!/usr/bin/env bash\n"
        "set +e\n"
        + helper
        + r'''python -m ruff "$@" 2>&1 | tee /tmp/paperagent-ruff.log
status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ] && [ "${1:-}" = "check" ]; then
  persist_failure /tmp/paperagent-ruff.log .github/evidence-bound-module-lint-failure.log 'chore(ci): record module lint failure'
fi
exit "$status"
''',
    )
    _write_executable(
        _WRAPPER_DIR / "pytest",
        "#!/usr/bin/env bash\n"
        "set +e\n"
        + helper
        + r'''python -m pytest "$@" 2>&1 | tee /tmp/paperagent-pytest.log
status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ] && printf '%s\n' "$*" | grep -q 'test_method_design_draft.py'; then
  persist_failure /tmp/paperagent-pytest.log .github/evidence-bound-module-test-failure.log 'chore(ci): record module test failure'
fi
exit "$status"
''',
    )
    with Path(github_path).open("a", encoding="utf-8") as handle:
        handle.write(str(_WRAPPER_DIR) + "\n")


def main() -> None:
    try:
        apply_all()
        apply_remaining()
        apply_lint_repairs()
        apply_test_repairs()
        _install_ci_wrappers()
    except BaseException:
        rendered = traceback.format_exc()
        _persist_failure(rendered)
        raise


if __name__ == "__main__":
    main()
