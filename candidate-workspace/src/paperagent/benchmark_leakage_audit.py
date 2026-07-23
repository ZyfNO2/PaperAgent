from __future__ import annotations

import ast
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
_CONDITIONED_DOMAIN_PHRASES = (
    "few-shot intent",
    "few shot intent",
    "multi-behavior recommendation",
    "multi behavior recommendation",
    "small object",
    "tiny object",
    "low-light pedestrian",
    "missing modality",
    "temporal order",
    "similar poses",
    "crowded scene",
    "visdrone",
)
_EVALUATION_CONTEXT_PHRASES = (
    "evaluator-facing labels",
    "grading keywords",
    "downstream scoring",
    "hidden benchmark answers",
    "grader notes",
    "hidden fixtures",
)
_SUSPICIOUS_CONSTANT = re.compile(
    r"^_(?:FEW_SHOT|MULTI_BEHAVIOR|SMALL_OBJECT|AERIAL|PLANT_DISEASE|"
    r"TIME_SERIES_ANOMALY|RECOMMENDATION)_.*\s*=",
    re.MULTILINE,
)
_SCAN_SUFFIXES = {".py", ".md"}
_SCAN_EXCLUSIONS = {"benchmark_leakage_audit.py"}


class LeakageAuditResult(FrozenModel):
    passed: bool
    findings: tuple[str, ...] = ()


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _python_constant_findings(path: Path, relative_path: str) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"source_syntax_error:{relative_path}:{exc.lineno}"]
    findings: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and _SUSPICIOUS_CONSTANT.match(f"{target.id} ="):
                findings.append(f"conditioned_constant:{relative_path}:{target.id}")
    return findings


def audit_benchmark_execution_boundary() -> LeakageAuditResult:
    """Scan the complete production package for benchmark-conditioned execution logic."""

    findings: list[str] = []
    for module_name in _FORBIDDEN_MODULES:
        if importlib.util.find_spec(module_name) is not None:
            findings.append(f"forbidden_module:{module_name}")

    from paperagent.claw_benchmark_runtime import execute_benchmark_case

    parameters = set(inspect.signature(execute_benchmark_case).parameters)
    for parameter in sorted(parameters & _FORBIDDEN_EXECUTOR_PARAMETERS):
        findings.append(f"gold_executor_parameter:{parameter}")

    root = _package_root()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in _SCAN_SUFFIXES or path.name in _SCAN_EXCLUSIONS:
            continue
        relative_path = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        normalized = text.casefold()
        if _CASE_ID.search(text):
            findings.append(f"case_id_in_production_source:{relative_path}")
        for phrase in _CONDITIONED_DOMAIN_PHRASES:
            if phrase in normalized:
                findings.append(f"conditioned_domain_phrase:{relative_path}:{phrase}")
        if relative_path.startswith("prompts/"):
            for phrase in _EVALUATION_CONTEXT_PHRASES:
                if phrase in normalized:
                    findings.append(f"evaluation_context_in_prompt:{relative_path}:{phrase}")
        if path.suffix == ".py":
            findings.extend(_python_constant_findings(path, relative_path))

    unique = tuple(dict.fromkeys(findings))
    return LeakageAuditResult(passed=not unique, findings=unique)


__all__ = ["LeakageAuditResult", "audit_benchmark_execution_boundary"]
