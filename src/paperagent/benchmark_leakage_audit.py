from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

from paperagent.schemas.base import FrozenModel

_CASE_ID = re.compile(r"\bat-\d{3}(?:-[a-z0-9-]+)?\b", re.IGNORECASE)
_FORBIDDEN_MODULES = (
    "paperagent.literature.task_query_overrides",
    "paperagent.claw_pilot_policy",
    "paperagent.claw_trace_reconciliation",
)
_FORBIDDEN_EXECUTOR_PARAMETERS = {
    "case",
    "gold_case",
    "expected_decision",
    "hypothesis",
    "experiment_plan",
    "stop_conditions",
    "special_assertions",
}
_SOURCE_RULES: dict[str, tuple[str, ...]] = {
    "claw_benchmark_adapter.py": (
        "_has_actionable_recovery_path",
        "pilot_recommended is not None",
    ),
    "claw_benchmark_runtime.py": ("GoldCase", "reconcile_ledger_relevance"),
    "retrieval/prepare_search.py": ("override_task_query", "task_query_overrides"),
    "literature/query_refinement.py": (
        "MultiFusionNet",
        "few-shot intent classification prototypical network",
        "Chinese long document classification hierarchical transformer",
    ),
    "literature/query_concepts.py": (
        "_AERIAL_QUERY_HINTS",
        "_SKIN_QUERY_HINTS",
        "_MULTI_BEHAVIOR_RECOMMENDATION_QUERY_HINTS",
    ),
    "literature/specialized_guards.py": (
        "_PLANT_DISEASE_QUERY_TERMS",
        "_TIME_SERIES_ANOMALY_QUERY_TERMS",
        "_RECOMMENDATION_QUERY_TERMS",
    ),
    "prompts/v0_1/planning.md": (
        "exactly two consolidated required gaps",
        "role-explicit gap descriptions",
    ),
}


class LeakageAuditResult(FrozenModel):
    passed: bool
    findings: tuple[str, ...] = ()


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def audit_benchmark_execution_boundary() -> LeakageAuditResult:
    """Detect known test-conditioning paths before benchmark normalization.

    The audit checks executable structure rather than relying on trace defaults. It is
    intentionally narrow and deterministic: forbidden benchmark-only modules, gold-bearing
    executor parameters, case IDs in production retrieval sources, and previously observed
    case-conditioned rules all produce a hard-failure signal.
    """

    findings: list[str] = []
    for module_name in _FORBIDDEN_MODULES:
        if importlib.util.find_spec(module_name) is not None:
            findings.append(f"forbidden_module:{module_name}")

    from paperagent.claw_benchmark_runtime import execute_benchmark_case

    parameters = set(inspect.signature(execute_benchmark_case).parameters)
    for parameter in sorted(parameters & _FORBIDDEN_EXECUTOR_PARAMETERS):
        findings.append(f"gold_executor_parameter:{parameter}")

    root = _package_root()
    for relative_path, forbidden_terms in _SOURCE_RULES.items():
        path = root / relative_path
        if not path.is_file():
            findings.append(f"source_missing:{relative_path}")
            continue
        text = path.read_text(encoding="utf-8")
        if _CASE_ID.search(text):
            findings.append(f"case_id_in_production_source:{relative_path}")
        for term in forbidden_terms:
            if term in text:
                findings.append(f"conditioned_rule:{relative_path}:{term}")

    unique = tuple(dict.fromkeys(findings))
    return LeakageAuditResult(passed=not unique, findings=unique)


__all__ = ["LeakageAuditResult", "audit_benchmark_execution_boundary"]
