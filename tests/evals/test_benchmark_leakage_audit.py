from __future__ import annotations

from pathlib import Path

from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary
from paperagent.claw_benchmark_runtime import execute_benchmark_case


def test_live_execution_boundary_has_no_known_benchmark_conditioning() -> None:
    result = audit_benchmark_execution_boundary()
    assert result.passed, result.findings
    assert result.findings == ()


def test_executor_cannot_receive_gold_annotations() -> None:
    parameters = set(__import__("inspect").signature(execute_benchmark_case).parameters)
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
