from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

AUTHORING_SCHEMA = "paperagent.academic-tailoring-retrieval.authoring.v1"
PUBLIC_SCHEMA = "paperagent.academic-tailoring-retrieval.public.v1"
FORBIDDEN_PUBLIC_KEYS = {
    "gold",
    "expected_assets",
    "baseline_decision",
    "reference_hypothesis",
    "compatibility_judgment",
    "minimal_method",
    "experiments",
    "stop_conditions",
    "allowed_alternatives",
    "hard_failures",
    "cases_sha256",
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("dataset root must be an object")
    return raw


def _assert_no_forbidden_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                raise ValueError(f"forbidden key {key!r} present at {path}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _validate_authoring(dataset: dict[str, Any]) -> None:
    if dataset.get("schema") != AUTHORING_SCHEMA:
        raise ValueError("unexpected authoring schema")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("authoring dataset must contain exactly 10 cases")
    case_ids: list[str] = []
    domains: list[str] = []
    counts: dict[str, int] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        case_id = case.get("case_id")
        case_type = case.get("case_type")
        domain = case.get("domain")
        public_input = case.get("public_input")
        gold = case.get("gold")
        if not all(isinstance(item, str) and item for item in (case_id, case_type, domain)):
            raise ValueError("case_id, case_type, and domain must be non-empty strings")
        if not isinstance(public_input, dict) or not isinstance(gold, dict):
            raise ValueError(f"{case_id}: public_input and gold must be objects")
        user_input = public_input.get("user_input")
        materials = public_input.get("supplied_materials", [])
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError(f"{case_id}: user_input must be non-empty")
        if not isinstance(materials, list) or len(materials) > 2:
            raise ValueError(f"{case_id}: supplied_materials must be a list of at most two items")
        case_ids.append(case_id)
        domains.append(domain)
        counts[case_type] = counts.get(case_type, 0) + 1
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case IDs must be unique")
    if len(domains) != len(set(domains)):
        raise ValueError("domains must be unique")
    expected_counts = {
        "title_only": 4,
        "baseline_with_condition": 3,
        "baseline_plus_parallel_paper": 3,
    }
    if counts != expected_counts:
        raise ValueError(f"unexpected case type distribution: {counts}")
    rubric = dataset.get("rubric")
    if not isinstance(rubric, dict) or not isinstance(rubric.get("weights"), dict):
        raise ValueError("rubric weights are required")
    if sum(int(value) for value in rubric["weights"].values()) != 100:
        raise ValueError("rubric weights must total 100")


def project_public_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    _validate_authoring(dataset)
    cases: list[dict[str, Any]] = []
    for case in dataset["cases"]:
        public_input = case["public_input"]
        materials = public_input.get("supplied_materials", [])
        titles: list[str] = []
        roles: list[str] = []
        for material in materials:
            if not isinstance(material, dict):
                raise ValueError(f"{case['case_id']}: supplied material must be an object")
            title = material.get("title")
            role = material.get("declared_role")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"{case['case_id']}: supplied title must be non-empty")
            if not isinstance(role, str) or not role.strip():
                raise ValueError(f"{case['case_id']}: supplied role must be non-empty")
            titles.append(title)
            roles.append(role)
        cases.append(
            {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "domain": case["domain"],
                "benchmark_input": {
                    "user_input": public_input["user_input"],
                    "supplied_material_titles": titles,
                    "user_declared_roles": roles,
                    "declared_constraints": [],
                },
            }
        )
    public = {
        "schema": PUBLIC_SCHEMA,
        "dataset_id": dataset["dataset_id"],
        "source_authoring_sha256": _sha256(dataset),
        "candidate_contract": {
            "executor_fields": [
                "benchmark_input.user_input",
                "benchmark_input.supplied_material_titles",
                "benchmark_input.user_declared_roles",
                "benchmark_input.declared_constraints",
            ],
            "case_metadata_not_forwarded_to_graph": ["case_id", "case_type", "domain"],
        },
        "cases": cases,
    }
    _assert_no_forbidden_keys(public)
    public["public_sha256"] = _sha256(public)
    return public


def _replace_gold_strings(value: object, *, counter: list[int]) -> object:
    if isinstance(value, dict):
        return {key: _replace_gold_strings(child, counter=counter) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_gold_strings(child, counter=counter) for child in value]
    if isinstance(value, str):
        counter[0] += 1
        return f"LEAK_CANARY_{counter[0]:05d}"
    return value


def verify_gold_mutation_invariance(dataset: dict[str, Any]) -> str:
    mutated = copy.deepcopy(dataset)
    counter = [0]
    for case in mutated["cases"]:
        case["gold"] = _replace_gold_strings(case["gold"], counter=counter)
    original_projection = project_public_dataset(dataset)
    mutated_projection = project_public_dataset(mutated)
    original_projection.pop("source_authoring_sha256", None)
    mutated_projection.pop("source_authoring_sha256", None)
    original_projection.pop("public_sha256", None)
    mutated_projection.pop("public_sha256", None)
    if _canonical_bytes(original_projection) != _canonical_bytes(mutated_projection):
        raise RuntimeError("Gold mutation changed the candidate-visible projection")
    return f"LEAK_CANARY_00001..LEAK_CANARY_{counter[0]:05d}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project the v1 authoring set into Gold-free inputs")
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    dataset = _load_json(args.authoring)
    canary_range = verify_gold_mutation_invariance(dataset)
    public = project_public_dataset(dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "paperagent.academic-tailoring-retrieval.boundary-report.v1",
        "authoring_sha256": _sha256(dataset),
        "public_sha256": public["public_sha256"],
        "case_count": len(public["cases"]),
        "gold_mutation_invariant": True,
        "canary_range": canary_range,
        "forbidden_key_scan_passed": True,
        "output": str(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
