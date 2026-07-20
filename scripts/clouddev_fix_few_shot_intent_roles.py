from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/few-shot-intent-roles"
STATUS = (
    ROOT
    / "evals/claw_academic_tailoring_v1/live-probes/few-shot-intent-role-gate-latest.json"
)
SOURCE = ROOT / "src/paperagent/evidence_gap_binding.py"
TEST = ROOT / "tests/review/test_few_shot_intent_role_binding.py"
GATE = ROOT / ".github/workflows/second-batch-retrieval-offline-gate.yml"


def run(name: str, command: list[str]) -> int:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    (OUT / f"{name}.log").write_text(
        completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    return completed.returncode


def patch_source() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    helper = r'''_METRIC_PATTERN = re.compile(
    r"\b(?:m?ap(?:50|75|_small)?|f1|auc|accuracy|precision|recall|fps|latency|"
    r"flops?|parameters?|params?|memory|energy|power)\b",
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
    "multi-label intent",
    "multilabel intent",
    "user intent",
)
_FEW_SHOT_CUES = (
    "few-shot",
    "few shot",
    "low-resource",
    "low resource",
    "k-shot",
    "few examples",
    "few utterances",
    "few annotated",
    "limited labeled",
    "limited training",
    "data scarcity",
    "scarce data",
    "prototypical",
    "prototype",
)


def _is_few_shot_intent_evidence(text: str) -> bool:
    return any(cue in text for cue in _FEW_SHOT_INTENT_TASK_CUES) and any(
        cue in text for cue in _FEW_SHOT_CUES
    )


def _few_shot_intent_baseline_support(text: str) -> bool:
    if not _is_few_shot_intent_evidence(text):
        return False
    evaluation = any(
        cue in text
        for cue in (
            "experiment",
            "experimental",
            "dataset",
            "benchmark",
            "evaluation",
            "evaluate",
            "test set",
            "validation set",
            "result",
            "performance",
            "accuracy",
            "f1",
        )
    )
    method_or_comparison = any(
        cue in text
        for cue in (
            "we propose",
            "we introduce",
            "framework",
            "network",
            "model",
            "approach",
            "method",
            "prototypical",
            "prototype",
            "nearest neighbor",
            "contrastive learning",
            "natural language inference",
            "baseline",
            "state-of-the-art",
            "outperform",
        )
    )
    return evaluation and method_or_comparison


def _few_shot_intent_mechanism_support(text: str) -> bool:
    if not _is_few_shot_intent_evidence(text):
        return False
    problem = any(
        cue in text
        for cue in (
            "data scarcity",
            "scarce data",
            "few annotated",
            "few examples",
            "few utterances",
            "limited labeled",
            "limited training",
            "insufficient training",
            "lack of training",
            "low-resource",
            "low resource",
            "overfitting",
            "noisy",
            "confusion",
            "semantically similar",
            "unseen intent",
            "out-of-scope",
            "out of scope",
            "oos detection",
            "threshold",
            "domain shift",
            "data-rich domains",
        )
    )
    intervention = any(
        cue in text
        for cue in (
            "we propose",
            "we introduce",
            "framework",
            "network",
            "prototypical",
            "prototype",
            "contrastive",
            "label semantics",
            "label name embedding",
            "label description",
            "calibration",
            "meta-learning",
            "natural language inference",
            "entailment",
            "nearest neighbor",
            "distance metric",
            "paraphras",
            "transfer",
        )
    )
    return problem and intervention


def _few_shot_intent_risk_support(text: str) -> bool:
    if not _is_few_shot_intent_evidence(text):
        return False
    return any(
        cue in text
        for cue in (
            "unknown intent",
            "unknown intents",
            "unseen intent",
            "out-of-scope",
            "out of scope",
            "oos detection",
            "open-set",
            "open set",
            "novel intent",
            "reject option",
            "rejection",
            "more challenging",
            "overfitting",
            "performance degradation",
            "data scarcity",
            "scarce data",
            "few annotated",
            "limited labeled",
        )
    )
'''
    pattern = re.compile(
        r'_METRIC_PATTERN = re\.compile\(\n.*?\n\)\n'
        r'(?:_FEW_SHOT_INTENT_TASK_CUES.*?\n)?'
        r'\n\ndef _dedupe',
        re.DOTALL,
    )
    replacement = helper + "\n\ndef _dedupe"
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("could not replace metric/helper section")

    patches = (
        (
            'def _baseline_role_support(text: str) -> bool:\n'
            '    evaluation_context = any(\n',
            'def _baseline_role_support(text: str) -> bool:\n'
            '    if _few_shot_intent_baseline_support(text):\n'
            '        return True\n'
            '    evaluation_context = any(\n',
        ),
        (
            'def _mechanism_role_support(text: str) -> bool:\n'
            '    problem = any(\n',
            'def _mechanism_role_support(text: str) -> bool:\n'
            '    if _few_shot_intent_mechanism_support(text):\n'
            '        return True\n'
            '    problem = any(\n',
        ),
        (
            'def _risk_role_support(text: str) -> bool:\n'
            '    return any(\n',
            'def _risk_role_support(text: str) -> bool:\n'
            '    if _few_shot_intent_risk_support(text):\n'
            '        return True\n'
            '    return any(\n',
        ),
    )
    for old, new in patches:
        if new in updated:
            continue
        if old not in updated:
            raise RuntimeError(f"expected role function fragment not found: {old!r}")
        updated = updated.replace(old, new, 1)
    SOURCE.write_text(updated, encoding="utf-8")


def write_test() -> None:
    TEST.write_text(
        r'''from __future__ import annotations

from datetime import UTC, datetime

from paperagent.evidence_gap_binding import build_evidence_ledger
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.plan import SearchQuery


def _plan() -> ResearchPlan:
    gaps = [
        EvidenceGap(
            gap_id="baseline_comparison",
            description="小样本行业文本意图识别的可复现基线与强比较证据。",
        ),
        EvidenceGap(
            gap_id="mechanism_limitation",
            description="小样本意图识别的数据稀缺机制、领域适配方法与局限。",
        ),
        EvidenceGap(
            gap_id="risk_negative_evidence",
            description="小样本意图识别的开放集风险、失败案例与负面证据。",
            required=False,
            minimum_accepted_items=0,
        ),
    ]
    queries = [
        SearchQuery(
            query_id="q1",
            gap_id="baseline_comparison",
            query="few-shot intent classification prototypical network",
            source_types=["paper"],
        ),
        SearchQuery(
            query_id="q2",
            gap_id="mechanism_limitation",
            query="few-shot intent classification contrastive learning label semantics",
            source_types=["paper"],
        ),
        SearchQuery(
            query_id="q3",
            gap_id="risk_negative_evidence",
            query="few-shot intent detection open set out-of-scope",
            source_types=["paper"],
        ),
    ]
    return ResearchPlan(
        status="ready",
        problem_statement="小样本行业文本意图识别",
        scope="few-shot text intent classification and open-set intent detection",
        evidence_gaps=gaps,
        search_queries=queries,
        success_criteria=["找到任务匹配的基线、机制和风险证据"],
        risks=["类别混淆、数据稀缺与开放集意图"],
    )


def _item(
    *,
    evidence_id: str,
    gap_id: str,
    query: str,
    title: str,
    summary: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"doi:10.1000/{evidence_id}",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[gap_id],
        summary=summary,
        content_hash=f"sha256:{evidence_id}",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": gap_id, "query_text": query},
    )


def _bundle(items: list[EvidenceItem]) -> EvidenceBundle:
    return EvidenceBundle(
        items=items,
        accepted_ids=[item.evidence_id for item in items],
        identity_verified_ids=[item.evidence_id for item in items],
        coverage_by_gap={item.supports_gap_ids[0]: 1 for item in items},
    )


def test_case_011_wording_binds_each_origin_role_without_relaxing_provenance() -> None:
    items = [
        _item(
            evidence_id="ev-baseline",
            gap_id="baseline_comparison",
            query="few-shot intent classification prototypical network",
            title="Semantic Transportation Prototypical Network for Few-Shot Intent Detection",
            summary=(
                "Few-shot intent detection has few annotated utterances and confusion among "
                "semantically similar intents. We propose a semantic transportation prototypical "
                "network. Experiments on two benchmark datasets evaluate its classification "
                "performance against existing methods."
            ),
        ),
        _item(
            evidence_id="ev-mechanism",
            gap_id="mechanism_limitation",
            query="few-shot intent classification contrastive learning label semantics",
            title="Few-shot Learning for Multi-label Intent Detection",
            summary=(
                "Few-shot user intent detection has only a few examples per label. We introduce "
                "label name embedding and nonparametric threshold calibration transferred from "
                "data-rich domains. Experiments report improved multi-label intent performance."
            ),
        ),
        _item(
            evidence_id="ev-risk",
            gap_id="risk_negative_evidence",
            query="few-shot intent detection open set out-of-scope",
            title=(
                "Discriminative Nearest Neighbor Few-Shot Intent Detection by Transferring "
                "Natural Language Inference"
            ),
            summary=(
                "Few-shot intent detection is limited by scarce training data, while out-of-scope "
                "detection is more challenging. The method transfers natural language inference "
                "and uses a nearest-neighbor distance mechanism for in-domain and OOS evaluation."
            ),
        ),
    ]

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="小样本行业文本意图识别"),
        plan=_plan(),
        evidence=_bundle(items),
    )

    assert set(ledger.accepted_ids) == {"ev-baseline", "ev-mechanism", "ev-risk"}
    direct = {
        (support.evidence_id, support.gap_id): support
        for support in supports
        if support.checklist_results.get("query_provenance_match")
    }
    assert direct[("ev-baseline", "baseline_comparison")].decision == "accept"
    assert direct[("ev-mechanism", "mechanism_limitation")].decision == "accept"
    assert direct[("ev-risk", "risk_negative_evidence")].decision == "accept"
    for support in direct.values():
        assert support.checklist_results["role_evidence_present"] is True
        assert support.checklist_results["required_concepts_match"] is True


def test_visual_few_shot_paper_remains_rejected_for_intent_baseline() -> None:
    full_plan = _plan()
    plan = full_plan.model_copy(
        update={
            "evidence_gaps": [full_plan.evidence_gaps[0]],
            "search_queries": [full_plan.search_queries[0]],
        }
    )
    item = _item(
        evidence_id="ev-image",
        gap_id="baseline_comparison",
        query="few-shot intent classification prototypical network",
        title="Meta-Baseline for Few-Shot Image Classification",
        summary=(
            "A prototypical network is evaluated on image classification benchmark datasets "
            "and outperforms visual baselines."
        ),
    )

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="小样本行业文本意图识别"),
        plan=plan,
        evidence=_bundle([item]),
    )

    assert ledger.accepted_ids == []
    binding = next(support for support in supports if support.gap_id == "baseline_comparison")
    assert binding.decision == "reject"
    assert binding.checklist_results["required_concepts_match"] is False


def test_method_only_intent_paper_without_evaluation_is_not_a_baseline() -> None:
    full_plan = _plan()
    plan = full_plan.model_copy(
        update={
            "evidence_gaps": [full_plan.evidence_gaps[0]],
            "search_queries": [full_plan.search_queries[0]],
        }
    )
    item = _item(
        evidence_id="ev-no-eval",
        gap_id="baseline_comparison",
        query="few-shot intent classification prototypical network",
        title="A Prototypical Network for Few-Shot Intent Detection",
        summary="We propose a network for few-shot intent detection with few examples.",
    )

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="小样本行业文本意图识别"),
        plan=plan,
        evidence=_bundle([item]),
    )

    assert ledger.accepted_ids == []
    binding = next(support for support in supports if support.gap_id == "baseline_comparison")
    assert binding.checklist_results["role_evidence_present"] is False
''',
        encoding="utf-8",
    )


def restore_gate() -> None:
    GATE.write_text(
        r'''name: Retrieval Precision Offline Gate
# Validates task precision, durable executed-query provenance, and evidence binding.

on:
  push:
    branches:
      - feat/claw-live-search-runtime
    paths:
      - ".github/workflows/second-batch-retrieval-offline-gate.yml"
      - "src/paperagent/evidence_relevance.py"
      - "src/paperagent/evidence_gap_binding.py"
      - "src/paperagent/literature/adapter.py"
      - "src/paperagent/literature/query_concepts.py"
      - "src/paperagent/literature/query_refinement.py"
      - "src/paperagent/literature/ranking.py"
      - "src/paperagent/literature/specialized_guards.py"
      - "src/paperagent/literature/task_query_overrides.py"
      - "src/paperagent/retrieval/prepare_search.py"
      - "src/paperagent/retrieval/verify_evidence.py"
      - "tests/literature/test_prepared_query_contract.py"
      - "tests/literature/test_second_batch_query_precision.py"
      - "tests/literature/test_third_batch_query_precision.py"
      - "tests/literature/test_qa_hallucination_precision.py"
      - "tests/review/test_action_mechanism_binding.py"
      - "tests/review/test_few_shot_intent_role_binding.py"
      - "tests/review/test_low_light_mechanism_binding.py"
      - "tests/review/test_research_contract_priority.py"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: retrieval-precision-offline
  cancel-in-progress: true

jobs:
  verify:
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: pyproject.toml
      - name: Install project
        run: python -m pip install -q -e '.[dev]'
      - name: Run retrieval precision checks
        shell: bash
        run: |
          set +e
          out="build/retrieval-precision"
          mkdir -p "$out"
          files=(
            src/paperagent/evidence_relevance.py
            src/paperagent/evidence_gap_binding.py
            src/paperagent/literature/adapter.py
            src/paperagent/literature/query_concepts.py
            src/paperagent/literature/query_refinement.py
            src/paperagent/literature/ranking.py
            src/paperagent/literature/specialized_guards.py
            src/paperagent/literature/task_query_overrides.py
            src/paperagent/retrieval/prepare_search.py
            src/paperagent/retrieval/verify_evidence.py
            tests/literature/test_prepared_query_contract.py
            tests/literature/test_second_batch_query_precision.py
            tests/literature/test_third_batch_query_precision.py
            tests/literature/test_qa_hallucination_precision.py
            tests/review/test_action_mechanism_binding.py
            tests/review/test_few_shot_intent_role_binding.py
            tests/review/test_low_light_mechanism_binding.py
            tests/review/test_research_contract_priority.py
          )
          ruff check "${files[@]}" --output-format=concise > "$out/ruff.log" 2>&1
          ruff_status=$?
          ruff format --check --diff "${files[@]}" > "$out/format.log" 2>&1
          format_status=$?
          mypy --config-file pyproject.toml > "$out/mypy.log" 2>&1
          mypy_status=$?
          pytest -q \
            tests/literature/test_prepared_query_contract.py \
            tests/literature/test_second_batch_query_precision.py \
            tests/literature/test_third_batch_query_precision.py \
            tests/literature/test_qa_hallucination_precision.py \
            tests/literature/test_query_concepts.py \
            tests/literature/test_query_refinement.py \
            tests/review/test_action_mechanism_binding.py \
            tests/review/test_few_shot_intent_role_binding.py \
            tests/review/test_low_light_mechanism_binding.py \
            tests/review/test_semantic_gap_binding.py \
            tests/review/test_consolidated_regressions.py \
            tests/review/test_research_contract_priority.py \
            tests/nodes/test_retrieval.py \
            > "$out/pytest.log" 2>&1
          pytest_status=$?
          target="evals/claw_academic_tailoring_v1/live-probes/second-batch-retrieval-gate-latest.json"
          mkdir -p "$(dirname "$target")"
          python - "$target" "$ruff_status" "$format_status" "$mypy_status" "$pytest_status" <<'PY'
          import json
          import os
          import sys

          payload = {
              "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
              "workflow_head_sha": os.environ["GITHUB_SHA"],
              "ruff": int(sys.argv[2]),
              "format": int(sys.argv[3]),
              "mypy": int(sys.argv[4]),
              "pytest": int(sys.argv[5]),
          }
          payload["passed"] = all(
              payload[key] == 0 for key in ("ruff", "format", "mypy", "pytest")
          )
          with open(sys.argv[1], "w", encoding="utf-8") as handle:
              json.dump(payload, handle, indent=2, sort_keys=True)
              handle.write("\n")
          PY
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add "$target"
          git commit -m "chore(search): persist retrieval precision gate [skip ci]" || true
          git pull --rebase origin feat/claw-live-search-runtime
          git push origin HEAD:feat/claw-live-search-runtime
          if (( ruff_status || format_status || mypy_status || pytest_status )); then
            exit 1
          fi
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: retrieval-precision-${{ github.run_id }}
          path: build/retrieval-precision/
          if-no-files-found: error
          retention-days: 30
''',
        encoding="utf-8",
    )


def commit_result() -> None:
    subprocess.run(
        ["git", "config", "user.name", "github-actions[bot]"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ],
        cwd=ROOT,
        check=True,
    )
    for temporary in (
        ROOT / ".github/workflows/fix-few-shot-intent-binding-once.yml",
        ROOT / ".github/workflows/add-few-shot-intent-binding-once.yml",
    ):
        if temporary.exists():
            temporary.unlink()
    subprocess.run(
        [
            "git",
            "add",
            "-A",
            str(SOURCE.relative_to(ROOT)),
            str(TEST.relative_to(ROOT)),
            str(GATE.relative_to(ROOT)),
            str(STATUS.relative_to(ROOT)),
            "scripts/clouddev_fix_few_shot_intent_roles.py",
            ".github/workflows/fix-few-shot-intent-binding-once.yml",
            ".github/workflows/add-few-shot-intent-binding-once.yml",
        ],
        cwd=ROOT,
        check=True,
    )
    Path(__file__).unlink()
    subprocess.run(
        ["git", "add", "-u", "scripts/clouddev_fix_few_shot_intent_roles.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "fix(evidence): bind Case 011 intent evidence and restore gate",
        ],
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    patch_source()
    write_test()
    restore_gate()
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
                "tests/literature/test_qa_hallucination_precision.py",
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
    STATUS.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not payload["passed"]:
        raise SystemExit(1)
    commit_result()


if __name__ == "__main__":
    main()
