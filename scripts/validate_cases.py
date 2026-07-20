#!/usr/bin/env python3
"""Dependency-free validator for Academic Method Holdout v2 JSONL files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "paperagent.academic-holdout.case.v2"
DECISIONS = {"GO", "REVISE", "NO_GO"}
CAPABILITIES = {
    "baseline_reproducibility",
    "strong_comparator",
    "evidence_role_binding",
    "interface_compatibility",
    "falsifiable_novelty",
    "negative_results",
    "material_identity",
    "pilot_gate",
}
ROLES = {"baseline", "strong_comparator", "mechanism", "risk", "supplied_material"}
LANGUAGES = {"zh", "en", "ja", "mixed"}
OLD_BENCHMARK_TERMS = {
    "few-shot intent",
    "multi-behavior recommendation",
    "small object",
    "tiny object",
    "low-light",
    "visdrone",
    "uav",
    "小目标",
    "低光",
}


class ValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _nonempty_strings(value: Any, field: str) -> list[str]:
    _require(isinstance(value, list) and value, f"{field} must be a non-empty list")
    _require(
        all(isinstance(item, str) and item.strip() for item in value),
        f"{field} must contain non-empty strings",
    )
    return value


def validate_case(case: dict[str, Any], *, public: bool) -> None:
    _require(
        set(case) == {"schema", "case_id", "input", "oracle", "metadata"},
        "unexpected top-level fields",
    )
    _require(case["schema"] == SCHEMA, "unexpected schema")
    case_id = case["case_id"]
    _require(isinstance(case_id, str) and case_id, "case_id must be non-empty")
    if public:
        _require(
            re.fullmatch(r"dev-\d{3}-[a-z0-9-]+", case_id) is not None,
            "invalid public case_id",
        )

    payload = case["input"]
    _require(
        set(payload) == {"user_request", "supplied_materials", "declared_constraints"},
        "unexpected input fields",
    )
    request = payload["user_request"]
    _require(isinstance(request, str) and request.strip(), "user_request must be non-empty")
    lowered = request.casefold()
    for term in OLD_BENCHMARK_TERMS:
        _require(
            term.casefold() not in lowered,
            f"legacy benchmark term found in user_request: {term}",
        )
    materials = payload["supplied_materials"]
    _require(
        isinstance(materials, list) and len(materials) <= 2,
        "supplied_materials must contain at most two entries",
    )
    for material in materials:
        _require(
            set(material) == {"title", "declared_role"},
            "unexpected supplied material fields",
        )
        _require(
            all(isinstance(material[key], str) and material[key].strip() for key in material),
            "invalid supplied material",
        )
    constraints = payload["declared_constraints"]
    _require(isinstance(constraints, list), "declared_constraints must be a list")
    _require(
        all(isinstance(item, str) and item.strip() for item in constraints),
        "invalid declared constraint",
    )

    oracle = case["oracle"]
    expected_oracle_fields = {
        "accepted_decisions",
        "required_findings",
        "forbidden_claims",
        "evidence_requirements",
        "pilot_allowed",
        "hard_failure_conditions",
    }
    _require(set(oracle) == expected_oracle_fields, "unexpected oracle fields")
    decisions = oracle["accepted_decisions"]
    _require(
        isinstance(decisions, list) and decisions and set(decisions) <= DECISIONS,
        "invalid accepted_decisions",
    )
    _require(len(decisions) == len(set(decisions)), "accepted_decisions must be unique")
    _nonempty_strings(oracle["required_findings"], "required_findings")
    _nonempty_strings(oracle["forbidden_claims"], "forbidden_claims")
    _require(isinstance(oracle["pilot_allowed"], bool), "pilot_allowed must be boolean")
    _require(
        isinstance(oracle["hard_failure_conditions"], list),
        "hard_failure_conditions must be a list",
    )
    _require(
        all(
            isinstance(item, str) and item.strip()
            for item in oracle["hard_failure_conditions"]
        ),
        "invalid hard failure",
    )
    requirements = oracle["evidence_requirements"]
    _require(
        isinstance(requirements, list) and requirements,
        "evidence_requirements must be non-empty",
    )
    seen_roles: set[str] = set()
    for requirement in requirements:
        _require(
            set(requirement) == {"role", "minimum_contract"},
            "unexpected evidence requirement fields",
        )
        role = requirement["role"]
        _require(role in ROLES, f"invalid evidence role: {role}")
        _require(role not in seen_roles, f"duplicate evidence role: {role}")
        seen_roles.add(role)
        _nonempty_strings(requirement["minimum_contract"], f"minimum_contract[{role}]")

    metadata = case["metadata"]
    _require(
        set(metadata)
        == {"split", "capability", "domain", "language", "metamorphic_group"},
        "unexpected metadata fields",
    )
    _require(metadata["capability"] in CAPABILITIES, "invalid capability")
    _require(metadata["language"] in LANGUAGES, "invalid language")
    _require(
        isinstance(metadata["domain"], str) and metadata["domain"].strip(),
        "invalid domain",
    )
    _require(
        metadata["metamorphic_group"] is None
        or isinstance(metadata["metamorphic_group"], str),
        "invalid metamorphic_group",
    )
    if public:
        _require(metadata["split"] == "development", "public cases must use development split")


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            case = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"line {line_number}: invalid JSON: {exc}") from exc
        _require(isinstance(case, dict), f"line {line_number}: case must be an object")
        try:
            validate_case(case, public=True)
        except ValidationError as exc:
            raise ValidationError(f"line {line_number}: {exc}") from exc
        cases.append(case)
    _require(cases, "dataset is empty")
    return cases


def validate_dataset(cases: list[dict[str, Any]]) -> None:
    ids = [case["case_id"] for case in cases]
    _require(len(ids) == len(set(ids)), "case IDs must be unique")
    _require(len(cases) == 12, "public development set must contain exactly 12 cases")
    capabilities = Counter(case["metadata"]["capability"] for case in cases)
    _require(set(capabilities) == CAPABILITIES, "all eight capabilities must be represented")
    domains = {case["metadata"]["domain"] for case in cases}
    _require(len(domains) >= 10, "public set must span at least ten domains")
    decisions = {
        decision
        for case in cases
        for decision in case["oracle"]["accepted_decisions"]
    }
    _require(decisions == DECISIONS, "public set must exercise GO, REVISE, and NO_GO")
    _require(
        any(case["oracle"]["pilot_allowed"] for case in cases),
        "at least one case must allow pilot",
    )
    _require(
        any(not case["oracle"]["pilot_allowed"] for case in cases),
        "at least one case must forbid pilot",
    )
    metamorphic = Counter(
        case["metadata"]["metamorphic_group"]
        for case in cases
        if case["metadata"]["metamorphic_group"] is not None
    )
    _require(
        all(count >= 2 for count in metamorphic.values()),
        "public metamorphic groups require at least two variants",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.path)
        validate_dataset(cases)
    except (OSError, ValidationError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"validated {len(cases)} cases from {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
