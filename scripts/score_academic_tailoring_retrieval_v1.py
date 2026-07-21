from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace

AUTHORING_SCHEMA = "paperagent.academic-tailoring-retrieval.authoring.v1"
FORBIDDEN_PROMPT_TERMS = {
    "expected_assets",
    "baseline_decision",
    "reference_hypothesis",
    "compatibility_judgment",
    "minimal_method",
    "allowed_alternatives",
    "hard_failures",
    "cases_sha256",
    "paperagent.academic-tailoring-retrieval.authoring.v1",
}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be an object")
    return raw


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError(f"{path}:{line_number}: row must be an object")
        rows.append(raw)
    return rows


def _flatten_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _flatten_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_strings(child)


def _normalize(value: str) -> str:
    return " ".join(TOKEN_RE.findall(value.casefold()))


def _title_matches(title: str, haystack: str) -> bool:
    normalized = _normalize(title)
    if normalized and normalized in haystack:
        return True
    tokens = set(normalized.split())
    if len(tokens) < 3:
        return False
    return len(tokens & set(haystack.split())) / len(tokens) >= 0.8


def _asset_matches(asset: dict[str, Any], state_text: str) -> bool:
    title = asset.get("title")
    if isinstance(title, str) and title.strip() and _title_matches(title, state_text):
        return True
    for key in ("doi", "arxiv", "url"):
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            normalized = _normalize(value)
            if normalized and normalized in state_text:
                return True
    return False


def _gold_only_phrases(case: dict[str, Any]) -> list[str]:
    gold = case.get("gold", {})
    phrases: list[str] = []
    for key in (
        "reference_hypothesis",
        "compatibility_judgment",
        "minimal_method",
        "experiments",
        "stop_conditions",
        "allowed_alternatives",
        "hard_failures",
    ):
        for text in _flatten_strings(gold.get(key)):
            if len(text) >= 32:
                phrases.append(text)
    return phrases


def _scan_prompts(
    cases_by_id: dict[str, dict[str, Any]], prompts: list[dict[str, Any]]
) -> list[str]:
    findings: list[str] = []
    for record in prompts:
        case_id = str(record.get("case_id", ""))
        messages = record.get("messages", [])
        prompt_text = "\n".join(_flatten_strings(messages))
        folded = prompt_text.casefold()
        for term in sorted(FORBIDDEN_PROMPT_TERMS):
            if term.casefold() in folded:
                findings.append(
                    f"{case_id}: forbidden evaluator term appeared in LLM prompt: {term}"
                )
        case = cases_by_id.get(case_id)
        if case is None:
            continue
        for phrase in _gold_only_phrases(case):
            if phrase in prompt_text:
                findings.append(f"{case_id}: exact Gold-only phrase appeared in LLM prompt")
                break
    return sorted(set(findings))


def _complete_hypothesis(trace: AcademicTailoringRunTrace) -> bool:
    hypothesis = trace.hypothesis
    if hypothesis is None:
        return False
    return all(
        isinstance(value, str) and bool(value.strip())
        for value in (
            hypothesis.condition,
            hypothesis.limitation,
            hypothesis.mechanism,
            hypothesis.intervention,
            hypothesis.target_metric,
            hypothesis.guardrail,
        )
    )


def _score_case(
    case: dict[str, Any],
    state: dict[str, Any] | None,
    trace: AcademicTailoringRunTrace | None,
    *,
    prompt_leakage: bool,
    minimum_score: int,
) -> dict[str, Any]:
    if state is None or trace is None:
        return {
            "case_id": case["case_id"],
            "score": 0,
            "minimum_score": minimum_score,
            "status": "failed",
            "dimensions": {},
            "hard_failures": ["runtime_error_or_missing_trace"],
        }

    gold = case["gold"]
    state_text = _normalize("\n".join(_flatten_strings(state)))
    expected_assets = [item for item in gold.get("expected_assets", []) if isinstance(item, dict)]
    paper_assets = [item for item in expected_assets if item.get("kind") == "paper"]
    repo_assets = [item for item in expected_assets if item.get("kind") == "repository"]
    dataset_assets = [item for item in expected_assets if item.get("kind") == "dataset"]
    matched_papers = sum(_asset_matches(item, state_text) for item in paper_assets)
    matched_repos = sum(_asset_matches(item, state_text) for item in repo_assets)
    matched_datasets = sum(_asset_matches(item, state_text) for item in dataset_assets)

    accepted_verified = [
        item
        for item in trace.evidence_reviews
        if item.accepted and item.identity_verified and item.relevance_passed
    ]
    accepted_repos = [item for item in accepted_verified if item.source_type == "repository"]
    baseline = trace.baseline

    identity_score = 0
    if accepted_verified:
        identity_score += 5
    if paper_assets:
        identity_score += round(10 * matched_papers / len(paper_assets))
    else:
        identity_score += 10
    identity_score = min(15, identity_score)

    baseline_score = 0
    if baseline is not None:
        baseline_score += 5
        baseline_decision = gold.get("baseline_decision", {})
        canonical = (
            baseline_decision.get("canonical") if isinstance(baseline_decision, dict) else None
        )
        supplied_titles = case.get("public_input", {}).get("supplied_materials", [])
        baseline_targets = [canonical] + [item.get("title") for item in supplied_titles]
        if any(
            isinstance(target, str) and _title_matches(target, _normalize(baseline.name))
            for target in baseline_targets
        ):
            baseline_score += 5
        if baseline.source_evidence_id:
            baseline_score += 2
        if baseline.version_or_commit:
            baseline_score += 3
        elif not baseline.reproduced:
            baseline_score += 1
    baseline_score = min(15, baseline_score)

    dataset_score = 0
    if dataset_assets:
        dataset_score += round(5 * matched_datasets / len(dataset_assets))
    elif baseline is not None and baseline.dataset:
        dataset_score += 5
    fact_count = sum(
        len(values)
        for values in (
            trace.fact_partitions.verified,
            trace.fact_partitions.inferred,
            trace.fact_partitions.proposed,
            trace.fact_partitions.unknown,
        )
    )
    if fact_count >= 3:
        dataset_score += 5
    dataset_score = min(10, dataset_score)

    repository_score = 0
    if repo_assets:
        repository_score += round(7 * matched_repos / len(repo_assets))
    elif accepted_repos:
        repository_score += 7
    if accepted_repos:
        repository_score += 3
    repository_score = min(10, repository_score)

    gap_score = 0
    if "gap" in trace.retrieval_roles:
        gap_score += 3
    if trace.fact_partitions.inferred or trace.fact_partitions.proposed:
        gap_score += 3
    if trace.stop_conditions:
        gap_score += 4
    gap_score = min(10, gap_score)

    module_score = 0
    if trace.modules:
        module_score += 3
        provenance_count = sum(bool(item.evidence_id) for item in trace.modules)
        role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
        module_score += round(4 * provenance_count / len(trace.modules))
        module_score += round(3 * role_count / len(trace.modules))
    elif trace.module_design_deferred and trace.module_defer_reason:
        module_score = 4
    module_score = min(10, module_score)

    compatibility_score = 0
    if trace.modules:
        semantic_count = sum(
            bool(item.input_semantics and item.output_semantics and item.failure_mode)
            for item in trace.modules
        )
        switch_count = sum(bool(item.implementation_switch) for item in trace.modules)
        compatible_count = sum(item.role_compatible is not False for item in trace.modules)
        compatibility_score += round(9 * semantic_count / len(trace.modules))
        compatibility_score += round(3 * switch_count / len(trace.modules))
        compatibility_score += round(3 * compatible_count / len(trace.modules))
    elif trace.module_design_deferred:
        compatibility_score = 5
    compatibility_score = min(15, compatibility_score)

    hypothesis_score = 5 if _complete_hypothesis(trace) else 0

    experiment_score = 0
    arm_types = {item.arm_type for item in trace.experiments}
    if "baseline" in arm_types:
        experiment_score += 2
    if arm_types & {"full", "single_module", "interaction"}:
        experiment_score += 2
    if "strong_comparison" in arm_types:
        experiment_score += 2
    if any(item.metrics for item in trace.experiments):
        experiment_score += 1
    if any(len(item.seeds) >= 3 or item.uncertainty_reporting for item in trace.experiments):
        experiment_score += 1
    if trace.stop_conditions or any(item.stopping_criteria for item in trace.experiments):
        experiment_score += 2
    experiment_score = min(10, experiment_score)

    dimensions = {
        "paper_identity_and_citation_truth": identity_score,
        "baseline_selection": baseline_score,
        "dataset_truth_and_task_fit": dataset_score,
        "repository_truth_and_relation": repository_score,
        "gap_analysis": gap_score,
        "module_provenance_and_role": module_score,
        "semantic_and_interface_compatibility": compatibility_score,
        "falsifiable_hypothesis": hypothesis_score,
        "experiment_and_ablation_design": experiment_score,
    }
    score = sum(dimensions.values())

    hard_failures: list[str] = []
    if prompt_leakage or trace.future_or_test_leakage:
        hard_failures.append("benchmark_leakage")
    if trace.fabricated_items:
        hard_failures.append("fabricated_item")
    if not accepted_verified:
        hard_failures.append("no_real_retrieval")
    if (
        baseline is not None
        and baseline.reproduced
        and not all(
            (
                baseline.version_or_commit,
                baseline.environment,
                baseline.split,
                baseline.reproduced_metric,
            )
        )
    ):
        hard_failures.append("repository_exists_claimed_as_reproduced")
    if any(item.role_compatible is False for item in trace.modules):
        hard_failures.append("unsupported_compatibility")
    if any(
        item.accepted and item.core_evidence and item.role in (None, "other")
        for item in trace.evidence_reviews
    ):
        hard_failures.append("evidence_role_mismatch")

    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "domain": case["domain"],
        "score": score,
        "minimum_score": minimum_score,
        "status": "passed" if score >= minimum_score and not hard_failures else "failed",
        "dimensions": dimensions,
        "matched_assets": {
            "papers": [matched_papers, len(paper_assets)],
            "repositories": [matched_repos, len(repo_assets)],
            "datasets": [matched_datasets, len(dataset_assets)],
        },
        "observed_decision": trace.decision,
        "hard_failures": sorted(set(hard_failures)),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score v1 candidate runs outside the executor")
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--runtime-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-score", type=int, default=80)
    parser.add_argument("--require-pass", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    authoring = _load_json(args.authoring)
    if authoring.get("schema") != AUTHORING_SCHEMA:
        raise ValueError("unexpected authoring schema")
    cases = authoring.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("authoring dataset must contain 10 cases")
    cases_by_id = {str(case["case_id"]): case for case in cases}

    states_by_id = {
        str(row["case_id"]): row["state"]
        for row in _load_jsonl(args.states)
        if isinstance(row.get("state"), dict)
    }
    traces_by_id: dict[str, AcademicTailoringRunTrace] = {}
    for row in _load_jsonl(args.traces):
        trace = AcademicTailoringRunTrace.model_validate(row)
        traces_by_id[trace.case_id] = trace
    prompts = _load_jsonl(args.prompts)
    prompt_findings = _scan_prompts(cases_by_id, prompts)
    prompt_cases = {finding.split(":", 1)[0] for finding in prompt_findings}
    runtime_summary = _load_json(args.runtime_summary)

    results = [
        _score_case(
            case,
            states_by_id.get(str(case["case_id"])),
            traces_by_id.get(str(case["case_id"])),
            prompt_leakage=str(case["case_id"]) in prompt_cases,
            minimum_score=args.minimum_score,
        )
        for case in cases
    ]
    passed = sum(item["status"] == "passed" for item in results)
    hard_failure_count = sum(len(item["hard_failures"]) for item in results)
    report = {
        "schema": "paperagent.academic-tailoring-retrieval.diagnostic-report.v1",
        "dataset_id": authoring.get("dataset_id"),
        "authoring_sha256": _sha256(authoring),
        "runtime_source_sha": runtime_summary.get("source_sha"),
        "evaluation_mode": "deterministic_development_diagnostic_not_formal_scientific_acceptance",
        "minimum_score": args.minimum_score,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "average_score": round(sum(item["score"] for item in results) / len(results), 2),
        "hard_failure_count": hard_failure_count,
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
    failed = (
        report["failed"] or hard_failure_count or prompt_findings or runtime_summary.get("errors")
    )
    return 1 if args.require_pass and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
