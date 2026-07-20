from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "src/paperagent/evidence_gap_binding.py"
WORKFLOW_PATH = ROOT / ".github/workflows/second-batch-retrieval-offline-gate.yml"
STATUS_PATH = ROOT / "evals/claw_academic_tailoring_v1/live-probes/case013-role-gate-latest.json"
SCRIPT_PATH = Path(__file__).resolve()


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:80]!r}")
    return text.replace(old, new)


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout[-12000:]


def patch_evidence_role() -> None:
    text = EVIDENCE_PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '            "complex environment",\n',
        '            "complex environment",\n'
        '            "hallucination",\n'
        '            "factual error",\n'
        '            "unsupported claim",\n'
        '            "confabulation",\n',
    )
    text = replace_once(
        text,
        '            "multimodal",\n        )\n    )\n    return problem and intervention\n',
        '            "multimodal",\n'
        '            "verification",\n'
        '            "uncertainty",\n'
        '            "self-check",\n'
        '            "retrieval",\n'
        '        )\n'
        '    )\n'
        '    survey_mechanism = (\n'
        '        any(cue in text for cue in ("review", "survey", "taxonomy"))\n'
        '        and "hallucination" in text\n'
        '        and any(\n'
        '            cue in text\n'
        '            for cue in ("cause", "mechanism", "challenge", "limitation", "factual error")\n'
        '        )\n'
        '    )\n'
        '    return (problem and intervention) or survey_mechanism\n',
    )
    EVIDENCE_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    statuses = {"patch": 99, "format": 99, "ruff": 99, "mypy": 99, "pytest": 99}
    logs: dict[str, str] = {}
    try:
        patch_evidence_role()
        statuses["patch"] = 0
        files = [
            "src/paperagent/evidence_gap_binding.py",
            "src/paperagent/literature/ranking.py",
            "src/paperagent/literature/specialized_guards.py",
            "src/paperagent/literature/task_query_overrides.py",
            "src/paperagent/retrieval/prepare_search.py",
            "tests/literature/test_qa_hallucination_precision.py",
        ]
        statuses["format"], logs["format"] = run(["ruff", "format", *files])
        statuses["ruff"], logs["ruff"] = run(["ruff", "check", *files])
        statuses["mypy"], logs["mypy"] = run(["mypy", "--config-file", "pyproject.toml"])
        statuses["pytest"], logs["pytest"] = run(
            [
                "pytest",
                "-q",
                "tests/literature/test_qa_hallucination_precision.py",
                "tests/literature/test_prepared_query_contract.py",
                "tests/literature/test_second_batch_query_precision.py",
                "tests/literature/test_third_batch_query_precision.py",
                "tests/review/test_action_mechanism_binding.py",
                "tests/review/test_low_light_mechanism_binding.py",
                "tests/review/test_semantic_gap_binding.py",
                "tests/review/test_consolidated_regressions.py",
                "tests/nodes/test_retrieval.py",
            ]
        )
    except Exception as exc:
        statuses["patch"] = 1
        logs["patch"] = f"{type(exc).__name__}: {exc}"

    passed = all(value == 0 for value in statuses.values())
    payload = {
        "passed": passed,
        "workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "workflow_head_sha": os.environ.get("GITHUB_SHA", ""),
        **statuses,
        "log_tails": {key: value[-4000:] for key, value in logs.items()},
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    subprocess.run(
        [
            "git",
            "show",
            "HEAD^:.github/workflows/second-batch-retrieval-offline-gate.yml",
        ],
        cwd=ROOT,
        check=True,
        stdout=WORKFLOW_PATH.open("w", encoding="utf-8"),
    )
    if not passed:
        subprocess.run(
            ["git", "restore", "src/paperagent/evidence_gap_binding.py"],
            cwd=ROOT,
            check=True,
        )
    SCRIPT_PATH.unlink(missing_ok=True)

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    message = (
        "fix(evidence): bind hallucination surveys to mechanism gaps"
        if passed
        else "chore(evidence): persist failed Case 013 role transaction [skip ci]"
    )
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
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
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
