from __future__ import annotations

import inspect
from pathlib import Path

from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary
from paperagent.claw_benchmark_runtime import execute_benchmark_case


def test_complete_production_tree_has_no_known_benchmark_conditioning() -> None:
    result = audit_benchmark_execution_boundary()
    assert result.passed, result.findings
    assert result.findings == ()


def test_audit_scans_every_python_and_prompt_source() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "paperagent"
    expected = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".md"}
    }
    assert "evidence_gap_binding.py" in expected
    assert "method_design_draft.py" in expected
    assert "literature/source_policy.py" in expected
    assert "prompts/v0_1/planning.md" in expected


def test_executor_cannot_receive_gold_annotations() -> None:
    parameters = set(inspect.signature(execute_benchmark_case).parameters)
    assert not parameters & {
        "case",
        "gold_case",
        "expected_decision",
        "hypothesis",
        "experiment_plan",
        "stop_conditions",
        "special_assertions",
    }


def test_removed_conditioning_modules_are_absent() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "paperagent"
    assert not (root / "literature" / "task_query_overrides.py").exists()
    assert not (root / "claw_pilot_policy.py").exists()
    assert not (root / "claw_trace_reconciliation.py").exists()
