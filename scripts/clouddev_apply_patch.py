from __future__ import annotations

import json
import os
import subprocess
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/clouddev-patch"
STATUS = ROOT / "evals/claw_academic_tailoring_v1/live-probes/case013-provenance-patch-latest.json"


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


def apply_patch() -> list[str]:
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

    return [
        "src/paperagent/literature/adapter.py",
        "src/paperagent/evidence_relevance.py",
        "src/paperagent/evidence_gap_binding.py",
        "tests/review/test_research_contract_priority.py",
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "workflow_head_sha": os.environ["GITHUB_SHA"],
    }
    try:
        files = apply_patch()
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
        payload.update(statuses)
        payload["passed"] = all(value == 0 for value in statuses.values())
        if not payload["passed"]:
            raise RuntimeError("one or more validation commands failed")

        STATUS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
        subprocess.run(
            ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(["git", "add", *files, str(STATUS.relative_to(ROOT))], cwd=ROOT, check=True)
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
    except Exception as exc:
        payload["passed"] = False
        payload["error"] = f"{type(exc).__name__}: {exc}"
        payload["traceback"] = traceback.format_exc().splitlines()[-12:]
        STATUS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
