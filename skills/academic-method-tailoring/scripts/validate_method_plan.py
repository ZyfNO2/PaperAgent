#!/usr/bin/env python3
"""Validate the structure and minimum integrity signals of a method-plan JSON file."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PLACEHOLDERS = {"", "...", "todo", "tbd", "unknown", "n/a", "none", None}
REQUIRED_TOP = {
    "topic",
    "problem",
    "baseline",
    "modules",
    "integration",
    "experiments",
    "claims",
    "risks",
    "decision",
}


def missing(mapping: dict[str, Any], keys: set[str], prefix: str) -> list[str]:
    errors: list[str] = []
    for key in sorted(keys):
        if key not in mapping or is_placeholder(mapping[key]):
            errors.append(f"{prefix}.{key} is required")
    return errors


def normalize(value: Any) -> Any:
    return value.strip().lower() if isinstance(value, str) else value


def is_placeholder(value: Any) -> bool:
    return value is None or (isinstance(value, str) and normalize(value) in PLACEHOLDERS)


def nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(not is_placeholder(item) for item in value)


def validate(plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors = missing(plan, REQUIRED_TOP, "plan")
    warnings: list[str] = []

    problem = plan.get("problem", {})
    if not isinstance(problem, dict):
        errors.append("plan.problem must be an object")
    else:
        errors += missing(problem, {"statement", "evidence", "metric", "guardrails"}, "problem")
        if not nonempty_list(problem.get("evidence")):
            errors.append("problem.evidence must contain at least one source")

    baseline = plan.get("baseline", {})
    if not isinstance(baseline, dict):
        errors.append("plan.baseline must be an object")
    else:
        errors += missing(
            baseline,
            {"name", "source", "version", "license", "reproducibility_status", "reproduced_metric"},
            "baseline",
        )
        if normalize(baseline.get("reproducibility_status")) != "verified":
            warnings.append("baseline is not marked verified; decision should normally be REVISE or NO-GO")

    modules = plan.get("modules")
    if not isinstance(modules, list) or not modules:
        errors.append("plan.modules must contain at least one module")
        modules = []
    for index, module in enumerate(modules):
        if not isinstance(module, dict):
            errors.append(f"modules[{index}] must be an object")
            continue
        errors += missing(
            module,
            {
                "name",
                "source",
                "license",
                "role",
                "input_contract",
                "output_contract",
                "hypothesis",
                "failure_mode",
            },
            f"modules[{index}]",
        )

    integration = plan.get("integration", {})
    if not isinstance(integration, dict):
        errors.append("plan.integration must be an object")
    else:
        errors += missing(
            integration,
            {"dataflow", "compatibility_checks", "loss", "baseline_fallback"},
            "integration",
        )
        checks = {normalize(item) for item in integration.get("compatibility_checks", []) if isinstance(item, str)}
        expected = {"semantic", "shape", "dtype", "scale", "ordering", "mask", "gradient"}
        omitted = sorted(expected - checks)
        if omitted:
            warnings.append("compatibility_checks omits: " + ", ".join(omitted))

    experiments = plan.get("experiments", {})
    if not isinstance(experiments, dict):
        errors.append("plan.experiments must be an object")
    else:
        errors += missing(
            experiments,
            {"datasets", "metrics", "comparisons", "ablations", "seeds", "stop_conditions"},
            "experiments",
        )
        for key in ("datasets", "metrics", "comparisons", "ablations", "stop_conditions"):
            if not nonempty_list(experiments.get(key)):
                errors.append(f"experiments.{key} must be a non-empty list")
        seeds = experiments.get("seeds")
        if not isinstance(seeds, int) or seeds < 1:
            errors.append("experiments.seeds must be a positive integer")
        elif seeds < 3:
            warnings.append("fewer than 3 seeds; justify the uncertainty strategy")
        ablation_text = " ".join(str(item).lower() for item in experiments.get("ablations", []))
        if len(modules) > 1 and not any(token in ablation_text for token in ("interaction", "full", "leave-one-out")):
            warnings.append("multiple modules but no explicit interaction/full/leave-one-out ablation")

    claims = plan.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("plan.claims must contain at least one claim")
    else:
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                errors.append(f"claims[{index}] must be an object")
                continue
            errors += missing(claim, {"claim", "evidence", "status", "falsifier"}, f"claims[{index}]")
            if not nonempty_list(claim.get("evidence")):
                errors.append(f"claims[{index}].evidence must be a non-empty list")

    decision = normalize(plan.get("decision"))
    if decision not in {"go", "revise", "no-go"}:
        errors.append("plan.decision must be GO, REVISE, or NO-GO")
    if warnings and decision == "go":
        warnings.append("GO has unresolved warnings; document why each warning is acceptable")

    return errors, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_method_plan.py <plan.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read valid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(plan, dict):
        print("ERROR: top-level JSON value must be an object", file=sys.stderr)
        return 2

    errors, warnings = validate(plan)
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")

    if errors:
        print(f"FAIL: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
