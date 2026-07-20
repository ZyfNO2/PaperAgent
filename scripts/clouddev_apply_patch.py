from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/clouddev-patch"
STATUS = ROOT / "evals/claw_academic_tailoring_v1/live-probes/second-batch-retrieval-gate-latest.json"
WORKFLOW = ROOT / ".github/workflows/second-batch-retrieval-offline-gate.yml"
SELF = Path(__file__).resolve()

PERMANENT_WORKFLOW = '''name: Retrieval Precision Offline Gate
# Validates task-specific precision contracts across controlled benchmark batches.

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
            tests/review/test_low_light_mechanism_binding.py \
            tests/review/test_semantic_gap_binding.py \
            tests/review/test_consolidated_regressions.py \
            tests/review/test_research_contract_priority.py \
            tests/nodes/test_retrieval.py \
            > "$out/pytest.log" 2>&1
          pytest_status=$?
          target="evals/claw_academic_tailoring_v1/live-probes/second-batch-retrieval-gate-latest.json"
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
          payload["passed"] = all(payload[key] == 0 for key in ("ruff", "format", "mypy", "pytest"))
          with open(sys.argv[1], "w", encoding="utf-8") as handle:
              json.dump(payload, handle, indent=2, sort_keys=True)
              handle.write("\\n")
          PY
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add "$target"
          git commit -m "chore(search): persist retrieval precision gate [skip ci]" || true
          git pull --rebase origin feat/claw-live-search-runtime
          git push origin HEAD:feat/claw-live-search-runtime
          if (( ruff_status || format_status || mypy_status || pytest_status )); then exit 1; fi
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: retrieval-precision-${{ github.run_id }}
          path: build/retrieval-precision/
          if-no-files-found: error
          retention-days: 30
'''


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise RuntimeError(f"expected source fragment not found in {path}")


def run(name: str, command: list[str]) -> int:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    (OUT / f"{name}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed.returncode


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    adapter = ROOT / "src/paperagent/literature/adapter.py"
    replace_once(
        adapter,
        '            metadata={\n                "verification_status": paper.verification_status,\n',
        '            metadata={\n                "query_text": query.query,\n                "verification_status": paper.verification_status,\n',
    )

    relevance = ROOT / "src/paperagent/evidence_relevance.py"
    replace_once(
        relevance,
        '    text = f"{item.title}\\n{item.summary}".lower()\n    matched = [term for term in contract.positive_terms if term in text]\n    negative = [term for term in contract.negative_terms if term in text]\n',
        '    text = f"{item.title}\\n{item.summary}".lower()\n    query_terms = _terms(item.metadata.get("query_text"))\n    positive_terms = _dedupe([*query_terms, *contract.positive_terms])\n    matched = [term for term in positive_terms if term in text]\n    negative = [term for term in contract.negative_terms if term in text]\n',
    )
    replace_once(
        relevance,
        '    strict_contract = len(contract.positive_terms) >= 2 or bool(domain_terms)\n',
        '    strict_contract = len(positive_terms) >= 2 or bool(domain_terms)\n',
    )
    replace_once(
        relevance,
        '    denominator = max(1, min(5, len(contract.positive_terms)))\n',
        '    denominator = max(1, min(5, len(positive_terms)))\n',
    )

    binding = ROOT / "src/paperagent/evidence_gap_binding.py"
    replace_once(
        binding,
        '    queries = tuple(value for value in query_texts if value.strip())\n',
        '    query_provenance = item.metadata.get("query_text", "").strip()\n    queries = tuple(value for value in (*query_texts, query_provenance) if value.strip())\n',
    )

    test = ROOT / "tests/review/test_research_contract_priority.py"
    text = test.read_text(encoding="utf-8")
    if "from paperagent.schemas.relevance import ResearchContract" not in text:
        text = text.replace(
            "from paperagent.schemas.plan import SearchQuery\n",
            "from paperagent.schemas.plan import SearchQuery\nfrom paperagent.schemas.relevance import ResearchContract\n",
            1,
        )
    if "test_executed_query_provenance_is_used_after_prepared_query_rotation" not in text:
        text += '''\n\ndef test_executed_query_provenance_is_used_after_prepared_query_rotation() -> None:
    item = EvidenceItem(
        evidence_id="ev-runtime-query",
        source_type="paper",
        title="Semantic Entropy Probes for Hallucination Detection",
        locator="https://arxiv.org/abs/2406.15927",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["mechanism_limitations"],
        summary="The method detects hallucinations through semantic uncertainty estimates.",
        content_hash="sha256:runtime-query",
        provider="literature_retrieval",
        metadata={
            "candidate_gap_ids": "mechanism_limitations",
            "query_text": "semantic entropy probes hallucination detection uncertainty",
        },
    )
    contract = ResearchContract(
        positive_terms=["unrelatedplannerterm", "anotherplannerterm"],
        required_gap_ids=["mechanism_limitations"],
    )

    lexical = assess_lexical_relevance(item, contract)

    assert lexical.decision == "pass"
    assert {"semantic", "entropy", "hallucination"} <= set(lexical.matched_terms)
'''
    test.write_text(text, encoding="utf-8")

    files = [
        "src/paperagent/literature/adapter.py",
        "src/paperagent/evidence_relevance.py",
        "src/paperagent/evidence_gap_binding.py",
        "tests/review/test_research_contract_priority.py",
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
                "tests/review/test_research_contract_priority.py",
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
    STATUS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not payload["passed"]:
        raise SystemExit(1)

    WORKFLOW.write_text(PERMANENT_WORKFLOW, encoding="utf-8")
    SELF.unlink()
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
            ".github/workflows/second-batch-retrieval-offline-gate.yml",
            "src/paperagent/literature/adapter.py",
            "src/paperagent/evidence_relevance.py",
            "src/paperagent/evidence_gap_binding.py",
            "tests/review/test_research_contract_priority.py",
            "evals/claw_academic_tailoring_v1/live-probes/second-batch-retrieval-gate-latest.json",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["git", "rm", "scripts/clouddev_apply_patch.py"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fix(evidence): persist executed query provenance"],
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
