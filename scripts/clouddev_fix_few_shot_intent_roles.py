from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/few-shot-intent-roles"
STATUS = ROOT / "evals/claw_academic_tailoring_v1/live-probes/few-shot-intent-role-gate-latest.json"
SELF = Path(__file__).resolve()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    if new not in text:
        raise RuntimeError(f"expected source fragment not found in {path}")


def run(name: str, command: list[str]) -> int:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    (OUT / f"{name}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed.returncode


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / "src/paperagent/evidence_gap_binding.py"
    insert_after = '''_METRIC_PATTERN = re.compile(
    r"\\b(?:m?ap(?:50|75|_small)?|f1|auc|accuracy|precision|recall|fps|latency|"
    r"flops?|parameters?|params?|memory|energy|power)\\b",
    re.IGNORECASE,
)
'''
    addition = '''_METRIC_PATTERN = re.compile(
    r"\\b(?:m?ap(?:50|75|_small)?|f1|auc|accuracy|precision|recall|fps|latency|"
    r"flops?|parameters?|params?|memory|energy|power)\\b",
    re.IGNORECASE,
)
_FEW_SHOT_INTENT_TASK_CUES = (
    "few-shot intent",
    "few shot intent",
    "low-resource intent",
    "low resource intent",
    "intent classification",
    "intent detection",
    "intent recognition",
)
_FEW_SHOT_CUES = (
    "few-shot",
    "few shot",
    "low-resource",
    "low resource",
    "prototypical",
    "prototype",
)


def _few_shot_intent_role_support(role: str, text: str) -> bool:
    task_matched = any(cue in text for cue in _FEW_SHOT_INTENT_TASK_CUES)
    few_shot_matched = any(cue in text for cue in _FEW_SHOT_CUES)
    if not (task_matched and few_shot_matched):
        return False
    if role == "baseline":
        return any(
            cue in text
            for cue in (
                "prototypical",
                "prototype",
                "nearest neighbor",
                "supervised-contrastive",
                "supervised contrastive",
                "natural language inference",
                "framework",
                "network",
            )
        )
    if role == "mechanism":
        return any(
            cue in text
            for cue in (
                "contrastive",
                "label semantics",
                "label description",
                "natural language inference",
                "entailment",
                "prototype",
                "nearest neighbor",
                "paraphras",
                "transfer",
            )
        )
    if role == "risk":
        return any(
            cue in text
            for cue in (
                "unknown intent",
                "unknown intents",
                "out-of-scope",
                "out of scope",
                "open-set",
                "open set",
                "novel intent",
                "reject option",
                "rejection",
            )
        )
    return False
'''
    replace_once(source, insert_after, addition)

    replace_once(
        source,
        '''def _baseline_role_support(text: str) -> bool:
    evaluation_context = any(
''',
        '''def _baseline_role_support(text: str) -> bool:
    if _few_shot_intent_role_support("baseline", text):
        return True
    evaluation_context = any(
''',
    )
    replace_once(
        source,
        '''def _mechanism_role_support(text: str) -> bool:
    problem = any(
''',
        '''def _mechanism_role_support(text: str) -> bool:
    if _few_shot_intent_role_support("mechanism", text):
        return True
    problem = any(
''',
    )
    replace_once(
        source,
        '''def _risk_role_support(text: str) -> bool:
    return any(
''',
        '''def _risk_role_support(text: str) -> bool:
    if _few_shot_intent_role_support("risk", text):
        return True
    return any(
''',
    )

    test = ROOT / "tests/review/test_few_shot_intent_role_binding.py"
    test.write_text(
        '''from __future__ import annotations

import pytest

from paperagent.evidence_gap_binding import (
    _baseline_role_support,
    _mechanism_role_support,
    _risk_role_support,
)


@pytest.mark.parametrize(
    ("text", "checker"),
    [
        (
            "A semantic transportation prototypical network for few-shot intent detection.",
            _baseline_role_support,
        ),
        (
            "A supervised-contrastive learning framework for few-shot intent classification.",
            _mechanism_role_support,
        ),
        (
            "Few-shot intent detection with open-set unknown intents and out-of-scope rejection.",
            _risk_role_support,
        ),
    ],
)
def test_few_shot_intent_papers_support_their_declared_roles(text: str, checker: object) -> None:
    assert callable(checker)
    assert checker(text) is True


def test_visual_few_shot_method_does_not_gain_intent_baseline_support() -> None:
    text = "Meta-Baseline is a network for few-shot image classification on visual benchmarks."
    assert _baseline_role_support(text) is False
''',
        encoding="utf-8",
    )

    files = [
        "src/paperagent/evidence_gap_binding.py",
        "tests/review/test_few_shot_intent_role_binding.py",
    ]
    subprocess.run(["ruff", "format", *files], cwd=ROOT, check=True)
    statuses = {
        "ruff": run("ruff", ["ruff", "check", *files]),
        "format": run("format", ["ruff", "format", "--check", "--diff", *files]),
        "mypy": run("mypy", ["mypy", "--config-file", "pyproject.toml"]),
        "pytest": run(
            "pytest",
            [
                "pytest",
                "-q",
                "tests/review/test_few_shot_intent_role_binding.py",
                "tests/literature/test_third_batch_query_precision.py",
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
    subprocess.run(["git", "add", *files, str(STATUS.relative_to(ROOT))], cwd=ROOT, check=True)
    SELF.unlink()
    subprocess.run(["git", "rm", "scripts/clouddev_fix_few_shot_intent_roles.py"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fix(evidence): bind few-shot intent papers by task role"],
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
