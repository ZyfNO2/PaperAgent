from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/verify-syntax"
STATUS = ROOT / "evals/claw_academic_tailoring_v1/live-probes/verify-syntax-gate-latest.json"
SELF = Path(__file__).resolve()


def run(name: str, command: list[str]) -> int:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    (OUT / f"{name}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed.returncode


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = ROOT / "src/paperagent/retrieval/verify_evidence.py"
    text = path.read_text(encoding="utf-8")
    old = '''    runtime_by_id.update(
        query.query_id: query.query.strip()
        for query in prepared_queries
        if query.query.strip()
    )
'''
    new = '''    runtime_by_id.update(
        {
            query.query_id: query.query.strip()
            for query in prepared_queries
            if query.query.strip()
        }
    )
'''
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise RuntimeError("runtime query update block did not match expected source")

    subprocess.run(["ruff", "format", str(path.relative_to(ROOT))], cwd=ROOT, check=True)
    statuses = {
        "ruff": run("ruff", ["ruff", "check", "src/paperagent/retrieval/verify_evidence.py"]),
        "format": run(
            "format",
            ["ruff", "format", "--check", "--diff", "src/paperagent/retrieval/verify_evidence.py"],
        ),
        "mypy": run("mypy", ["mypy", "--config-file", "pyproject.toml"]),
        "pytest": run(
            "pytest",
            [
                "pytest",
                "-q",
                "tests/literature/test_qa_hallucination_precision.py",
                "tests/review/test_research_contract_priority.py",
                "tests/review/test_semantic_gap_binding.py",
                "tests/review/test_consolidated_regressions.py",
                "tests/nodes/test_retrieval.py",
            ],
        ),
    }
    payload = {
        "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "workflow_head_sha": os.environ["GITHUB_SHA"],
        **statuses,
        "passed": all(value == 0 for value in statuses.values()),
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not payload["passed"]:
        raise SystemExit(1)

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "add",
            "src/paperagent/retrieval/verify_evidence.py",
            str(STATUS.relative_to(ROOT)),
        ],
        cwd=ROOT,
        check=True,
    )
    SELF.unlink()
    subprocess.run(["git", "rm", "scripts/clouddev_fix_verify_syntax.py"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fix(evidence): recover runtime queries with valid mapping syntax"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["git", "pull", "--rebase", "origin", "feat/claw-live-search-runtime"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["git", "push", "origin", "HEAD:feat/claw-live-search-runtime"],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
