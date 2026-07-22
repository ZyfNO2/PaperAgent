from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace

_SCORER_PATH = Path(__file__).with_name("score_academic_tailoring_retrieval_v1.py")


def _load_scorer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "academic_tailoring_retrieval_v1_subset_delegate", _SCORER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load scorer from {_SCORER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(value: object) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score a selected subset using the v1 external evaluator"
    )
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--runtime-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--minimum-score", type=int, default=80)
    return parser


def main() -> int:
    args = _parser().parse_args()
    scorer = _load_scorer()
    authoring: dict[str, Any] = scorer._load_json(args.authoring)
    if authoring.get("schema") != scorer.AUTHORING_SCHEMA:
        raise ValueError("unexpected authoring schema")
    all_cases = authoring.get("cases")
    if not isinstance(all_cases, list) or len(all_cases) != 10:
        raise ValueError("authoring dataset must contain the canonical 10 cases")

    selected_ids = list(dict.fromkeys(str(value) for value in args.case_id))
    all_cases_by_id = {str(case["case_id"]): case for case in all_cases}
    missing = [case_id for case_id in selected_ids if case_id not in all_cases_by_id]
    if missing:
        raise ValueError(f"unknown case IDs: {missing}")
    cases = [all_cases_by_id[case_id] for case_id in selected_ids]
    cases_by_id = {str(case["case_id"]): case for case in cases}

    states_by_id = {
        str(row["case_id"]): row["state"]
        for row in scorer._load_jsonl(args.states)
        if isinstance(row.get("state"), dict)
    }
    traces_by_id: dict[str, AcademicTailoringRunTrace] = {}
    for row in scorer._load_jsonl(args.traces):
        trace = AcademicTailoringRunTrace.model_validate(row)
        traces_by_id[trace.case_id] = trace

    prompts = [
        row
        for row in scorer._load_jsonl(args.prompts)
        if str(row.get("case_id")) in cases_by_id
    ]
    prompt_findings = scorer._scan_prompts(cases_by_id, prompts)
    prompt_cases = {finding.split(":", 1)[0] for finding in prompt_findings}
    runtime_summary = scorer._load_json(args.runtime_summary)

    results = [
        scorer._score_case(
            case,
            states_by_id.get(str(case["case_id"])),
            traces_by_id.get(str(case["case_id"])),
            prompt_leakage=str(case["case_id"]) in prompt_cases,
            minimum_score=args.minimum_score,
        )
        for case in cases
    ]
    passed = sum(item["status"] == "passed" for item in results)
    hard_failure_label_count = sum(len(item["hard_failures"]) for item in results)
    hard_failure_case_count = sum(bool(item["hard_failures"]) for item in results)
    report = {
        "schema": "paperagent.academic-tailoring-retrieval.subset-diagnostic-report.v1",
        "dataset_id": authoring.get("dataset_id"),
        "selected_case_ids": selected_ids,
        "authoring_sha256": _sha256(authoring),
        "runtime_source_sha": runtime_summary.get("source_sha"),
        "evaluation_mode": "targeted_diagnostic_subset_not_formal_scientific_acceptance",
        "minimum_score": args.minimum_score,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "average_score": round(sum(item["score"] for item in results) / len(results), 2),
        "hard_failure_count": hard_failure_label_count,
        "hard_failure_label_count": hard_failure_label_count,
        "hard_failure_case_count": hard_failure_case_count,
        "prompt_leakage_findings": prompt_findings,
        "runtime_errors": runtime_summary.get("errors", []),
        "cases": results,
    }
    report["report_sha256"] = _sha256(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
