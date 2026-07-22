from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).parents[2] / "scripts" / "run_academic_tailoring_retrieval_v1.py"
_SPEC = importlib.util.spec_from_file_location("academic_tailoring_diagnostic_budgets", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_diagnostic_runner_defaults_favor_coverage() -> None:
    args = _MODULE._parser().parse_args(
        ["--dataset", "public.json", "--output-dir", "build/eval"]
    )

    assert args.max_llm_calls == 20
    assert args.max_retrieval_rounds == 4
    assert args.max_queries_per_round == 10
    assert args.max_method_repairs == 3
    assert args.max_evidence_items == 120
    assert args.provider_call_budget == 480


def test_diagnostic_runner_allows_explicit_budget_reduction() -> None:
    args = _MODULE._parser().parse_args(
        [
            "--dataset",
            "public.json",
            "--output-dir",
            "build/eval",
            "--max-llm-calls",
            "8",
            "--max-retrieval-rounds",
            "2",
            "--max-queries-per-round",
            "4",
            "--max-method-repairs",
            "1",
            "--max-evidence-items",
            "30",
            "--provider-call-budget",
            "120",
        ]
    )

    assert args.max_llm_calls == 8
    assert args.max_retrieval_rounds == 2
    assert args.max_queries_per_round == 4
    assert args.max_method_repairs == 1
    assert args.max_evidence_items == 30
    assert args.provider_call_budget == 120
