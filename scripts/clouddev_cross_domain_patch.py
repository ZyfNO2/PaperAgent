from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "evals/claw_academic_tailoring_v1/live-probes/cross-domain-method-patch-latest.json"
WORKFLOW_PATH = ROOT / ".github/workflows/method-design-draft-offline-gate.yml"
TRIGGER_PATH = ROOT / ".cross-domain-method-trigger"
SCRIPT_PATH = Path(__file__).resolve()

PERMANENT_WORKFLOW = '''name: Method Design Draft Offline Gate

on:
  push:
    branches:
      - feat/claw-live-search-runtime
    paths:
      - ".github/workflows/method-design-draft-offline-gate.yml"
      - "src/paperagent/academic_methodology.py"
      - "src/paperagent/method_design_draft.py"
      - "src/paperagent/nodes/_shared.py"
      - "src/paperagent/nodes/method_design.py"
      - "src/paperagent/prompts/v0_1/method_design.md"
      - "tests/methodology/test_method_design_draft.py"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: method-design-draft-offline
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
      - name: Run offline method-design checks
        shell: bash
        run: |
          set +e
          out="build/method-design-draft"
          mkdir -p "$out"
          files=(
            src/paperagent/academic_methodology.py
            src/paperagent/method_design_draft.py
            src/paperagent/nodes/_shared.py
            src/paperagent/nodes/method_design.py
            tests/methodology/test_method_design_draft.py
          )
          ruff check "${files[@]}" --output-format=concise > "$out/ruff.log" 2>&1
          ruff_status=$?
          ruff format --check --diff "${files[@]}" > "$out/format.log" 2>&1
          format_status=$?
          mypy --config-file pyproject.toml > "$out/mypy.log" 2>&1
          mypy_status=$?
          pytest -q \
            tests/methodology/test_method_design_draft.py \
            tests/methodology/test_evidence_binding.py \
            tests/graph/test_full_graph.py \
            tests/graph/test_hitl.py \
            tests/review/test_consolidated_regressions.py \
            > "$out/pytest.log" 2>&1
          pytest_status=$?
          target="evals/claw_academic_tailoring_v1/live-probes/method-design-draft-gate-latest.json"
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
          git commit -m "chore(method): persist draft gate [skip ci]"
          git pull --rebase origin feat/claw-live-search-runtime
          git push origin HEAD:feat/claw-live-search-runtime
          if (( ruff_status || format_status || mypy_status || pytest_status )); then
            exit 1
          fi
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: method-design-draft-${{ github.run_id }}
          path: build/method-design-draft/
          if-no-files-found: error
          retention-days: 30
'''

PATCHED_PATHS = [
    "src/paperagent/evidence_gap_binding.py",
    "src/paperagent/literature/query_refinement.py",
    "src/paperagent/method_design_draft.py",
    "tests/literature/test_second_batch_query_precision.py",
    "tests/methodology/test_method_design_draft.py",
]
NEW_TEST_PATH = "tests/review/test_review_baseline_binding.py"


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


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


def apply_patch() -> None:
    replace_once(
        "src/paperagent/evidence_gap_binding.py",
        "    return sum((evaluation_context, measured_result, comparison)) >= 2\n",
        dedent(
            '''\
                review_context = any(cue in text for cue in ("review", "survey", "taxonomy"))
                comparison_scope = any(
                    cue in text
                    for cue in (
                        "comparative analysis",
                        "fusion scheme",
                        "fusion technique",
                        "network architecture",
                        "quantitative comparison",
                    )
                )
                return sum((evaluation_context, measured_result, comparison)) >= 2 or (
                    review_context and comparison_scope
                )
            '''
        ),
    )
    replace_once(
        "src/paperagent/literature/query_refinement.py",
        dedent(
            '''\
                if _contains_any(role, _MEDICAL_FAILURE_ROLE_HINTS):
                    return f"{core} incomplete data limitations"
                if _contains_any(role, _MEDICAL_PARALLEL_ROLE_HINTS):
                    return f"{core} fusion techniques"
            '''
        ),
        dedent(
            '''\
                if _contains_any(role, _MEDICAL_PARALLEL_ROLE_HINTS):
                    return f"{core} fusion techniques"
                if _contains_any(role, _MEDICAL_FAILURE_ROLE_HINTS):
                    return f"{core} incomplete data limitations"
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        "def _hypothesis_sentence(draft: MethodDesignDraft) -> str:\n",
        dedent(
            '''\
                def _is_review_evidence(title: str, summary: str) -> bool:
                    text = f"{title} {summary}".casefold()
                    return any(cue in text for cue in ("review", "survey", "taxonomy"))


                def _hypothesis_sentence(draft: MethodDesignDraft) -> str:
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        dedent(
            '''\
                    preprocessing=(
                        "match image resolution, augmentation, normalization, tiling, post-processing, "
                        "and inference precision across arms"
                    ),
            '''
        ),
        dedent(
            '''\
                    preprocessing=(
                        "match input construction, preprocessing, normalization, post-processing, "
                        "and inference precision across arms"
                    ),
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        dedent(
            '''\
                dataset = grounded_dataset or (
                    "unresolved task-matched dataset; select and freeze a public UAV small-object "
                    "benchmark before the pilot"
                )
                baseline_name = primary.title
            '''
        ),
        dedent(
            '''\
                dataset = grounded_dataset or (
                    "unresolved task-matched public dataset; select and freeze the dataset, split, "
                    "and data fingerprint before the pilot"
                )
                review_primary = _is_review_evidence(primary.title, primary.summary)
                baseline_name = (
                    "unresolved task-matched baseline selected from accepted review evidence"
                    if review_primary
                    else primary.title
                )
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        dedent(
            '''\
                    version_or_commit=(
                        f"published source {primary.stable_identifier}; implementation commit unresolved"
                    ),
            '''
        ),
        dedent(
            '''\
                    version_or_commit=(
                        f"review source {primary.stable_identifier}; implementation baseline unresolved"
                        if review_primary
                        else f"published source {primary.stable_identifier}; implementation commit unresolved"
                    ),
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        dedent(
            '''\
                    input_shape=(
                        "shape-preserving detector feature map at the selected insertion point; "
                        "exact channels are resolved after the baseline is frozen"
                    ),
                    output_shape=(
                        "same spatial and channel contract required by the downstream baseline stage"
                    ),
            '''
        ),
        dedent(
            '''\
                    input_shape=(
                        "task-specific representation at the selected insertion point; exact dimensions "
                        "are resolved after the baseline is frozen"
                    ),
                    output_shape=(
                        "representation contract required by the downstream baseline stage"
                    ),
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        dedent(
            '''\
                    loss_terms=("inherit baseline detection losses and weights for the first pilot",),
                    gradient_expectation=(
                        "verify non-zero finite gradients in the module and connected detector path"
                    ),
            '''
        ),
        dedent(
            '''\
                    loss_terms=("inherit baseline task losses and weights for the first pilot",),
                    gradient_expectation=(
                        "verify non-zero finite gradients in the module and connected baseline path"
                    ),
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        "    metrics = _dedupe((draft.primary_metric, \"AP_small\", \"latency\"))\n",
        dedent(
            '''\
                task_text = f"{request.question} {plan.scope}".casefold()
                task_metrics = (
                    ("AP_small",)
                    if any(term in task_text for term in ("small object", "tiny object", "小目标"))
                    else ()
                )
                metrics = _dedupe((draft.primary_metric, *task_metrics, "latency"))
            '''
        ),
    )

    method_test = ROOT / "tests/methodology/test_method_design_draft.py"
    text = method_test.read_text(encoding="utf-8")
    marker = "def test_review_evidence_keeps_implementation_baseline_unresolved()"
    if marker not in text:
        text += dedent(
            '''\


                def test_review_evidence_keeps_implementation_baseline_unresolved() -> None:
                    state = _state()
                    evidence = state["evidence"]
                    plan = state["plan"]
                    assert evidence is not None
                    assert plan is not None
                    review = evidence.items[0].model_copy(
                        update={
                            "title": (
                                "A review of deep learning-based information fusion techniques for "
                                "multimodal medical image classification"
                            ),
                            "summary": (
                                "This review compares input, intermediate, attention-based, and output "
                                "fusion schemes for multimodal medical image classification and discusses "
                                "incomplete data limitations."
                            ),
                        }
                    )
                    medical_state = cast(
                        PaperAgentState,
                        {
                            **state,
                            "request": ResearchRequest(question="多模态医学影像融合分类"),
                            "plan": plan.model_copy(
                                update={
                                    "problem_statement": "multimodal medical image classification",
                                    "scope": "paired medical classification with unresolved modalities",
                                }
                            ),
                            "evidence": evidence.model_copy(update={"items": [review]}),
                        },
                    )
                    proposal = build_method_proposal(
                        medical_state,
                        _draft(
                            primary_metric="AUC",
                            reported_dataset=None,
                            reported_comparator=None,
                            module_name="gated_multimodal_fusion",
                            input_semantics="paired modality representations",
                            output_semantics="fused representation for a classification head",
                        ),
                    )
                    baseline = proposal.methodology_plan.baseline
                    module = proposal.methodology_plan.modules[0]
                    assert baseline.name.startswith("unresolved task-matched baseline")
                    assert "UAV" not in (baseline.dataset or "")
                    assert "detector" not in (module.input_shape or "").casefold()
                    assert "detector" not in " ".join(module.loss_terms).casefold()
                    metrics = {
                        metric
                        for experiment in proposal.methodology_plan.experiments
                        for metric in experiment.metrics
                    }
                    assert "AUC" in metrics
                    assert "AP_small" not in metrics
            '''
        )
        method_test.write_text(text, encoding="utf-8")

    query_test = ROOT / "tests/literature/test_second_batch_query_precision.py"
    text = query_test.read_text(encoding="utf-8")
    marker = "def test_parallel_medical_role_wins_over_limitation_words()"
    if marker not in text:
        text += dedent(
            '''\


                def test_parallel_medical_role_wins_over_limitation_words() -> None:
                    result = refine_search_query(
                        "multimodal medical image classification alternatives and limitations",
                        gap_id="parallel_methods_evidence",
                        gap_description="parallel methods, alternatives, and known limitations",
                        research_context="多模态医学影像融合分类",
                    )
                    assert result.query == "multimodal medical image classification fusion techniques"
            '''
        )
        query_test.write_text(text, encoding="utf-8")

    (ROOT / NEW_TEST_PATH).write_text(
        dedent(
            '''\
                from __future__ import annotations

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


                def test_review_can_support_baseline_candidate_comparison() -> None:
                    gap = EvidenceGap(
                        gap_id="baseline_comparison",
                        description="baseline candidates and strong comparison evidence",
                    )
                    plan = ResearchPlan(
                        status="ready",
                        problem_statement="multimodal medical image classification",
                        scope="paired multimodal medical classification",
                        evidence_gaps=[gap],
                        search_queries=[
                            SearchQuery(
                                query_id="q-review",
                                gap_id=gap.gap_id,
                                query="multimodal medical image classification information fusion",
                                source_types=["paper"],
                            )
                        ],
                        success_criteria=["identify defensible baseline candidates"],
                        risks=["implementation baseline remains unresolved"],
                    )
                    item = EvidenceItem(
                        evidence_id="ev-medical-review",
                        source_type="paper",
                        title=(
                            "A review of deep learning-based information fusion techniques for "
                            "multimodal medical image classification"
                        ),
                        locator="doi:10.1016/j.compbiomed.2024.108635",
                        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
                        verification_status="accepted",
                        supports_gap_ids=[gap.gap_id],
                        summary=(
                            "This review analyzes multimodal medical image classification and compares "
                            "input, intermediate, attention-based, and output fusion techniques, network "
                            "architectures, incomplete multimodal data, and limitations."
                        ),
                        content_hash="sha256:medical-review",
                        provider="literature_retrieval",
                        metadata={"candidate_gap_ids": gap.gap_id},
                    )
                    _, _, _, supports, ledger = build_evidence_ledger(
                        request=ResearchRequest(question="多模态医学影像融合分类"),
                        plan=plan,
                        evidence=EvidenceBundle(
                            items=[item],
                            accepted_ids=[item.evidence_id],
                            identity_verified_ids=[item.evidence_id],
                            coverage_by_gap={gap.gap_id: 1},
                        ),
                    )
                    support = next(value for value in supports if value.gap_id == gap.gap_id)
                    assert ledger.accepted_ids == [item.evidence_id]
                    assert support.decision == "accept"
                    assert support.checklist_results["role_evidence_present"] is True
            '''
        ),
        encoding="utf-8",
    )


def cleanup_and_commit(passed: bool, payload: dict[str, object]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    WORKFLOW_PATH.write_text(PERMANENT_WORKFLOW, encoding="utf-8")
    if not passed:
        subprocess.run(["git", "restore", *PATCHED_PATHS], cwd=ROOT, check=False)
        (ROOT / NEW_TEST_PATH).unlink(missing_ok=True)
    SCRIPT_PATH.unlink(missing_ok=True)
    TRIGGER_PATH.unlink(missing_ok=True)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    message = (
        "fix(method): preserve cross-domain baseline semantics"
        if passed
        else "chore(method): persist failed cross-domain transaction [skip ci]"
    )
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    subprocess.run(["git", "pull", "--rebase", "origin", "feat/claw-live-search-runtime"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "HEAD:feat/claw-live-search-runtime"], cwd=ROOT, check=True)


def main() -> int:
    logs: dict[str, str] = {}
    statuses = {"patch": 99, "format": 99, "ruff": 99, "mypy": 99, "pytest": 99}
    try:
        apply_patch()
        statuses["patch"] = 0
        files = [
            "src/paperagent/evidence_gap_binding.py",
            "src/paperagent/literature/query_refinement.py",
            "src/paperagent/method_design_draft.py",
            "tests/literature/test_second_batch_query_precision.py",
            "tests/methodology/test_method_design_draft.py",
            NEW_TEST_PATH,
        ]
        statuses["format"], logs["format"] = run(["ruff", "format", *files])
        statuses["ruff"], logs["ruff"] = run(["ruff", "check", *files])
        statuses["mypy"], logs["mypy"] = run(["mypy", "--config-file", "pyproject.toml"])
        statuses["pytest"], logs["pytest"] = run(
            [
                "pytest",
                "-q",
                "tests/literature/test_second_batch_query_precision.py",
                "tests/literature/test_query_refinement.py",
                "tests/methodology/test_method_design_draft.py",
                "tests/methodology/test_evidence_binding.py",
                NEW_TEST_PATH,
                "tests/review/test_semantic_gap_binding.py",
                "tests/review/test_action_mechanism_binding.py",
                "tests/review/test_consolidated_regressions.py",
                "tests/graph/test_full_graph.py",
                "tests/graph/test_hitl.py",
            ]
        )
    except Exception as exc:
        logs["patch"] = f"{type(exc).__name__}: {exc}"
        statuses["patch"] = 1
    passed = all(value == 0 for value in statuses.values())
    payload: dict[str, object] = {
        "passed": passed,
        "transaction_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "transaction_head_sha": os.environ.get("GITHUB_SHA", ""),
        **statuses,
        "log_tails": {key: value[-4000:] for key, value in logs.items()},
    }
    cleanup_and_commit(passed, payload)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
