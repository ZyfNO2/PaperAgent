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
_INFERRED_BASELINE_RELATIONS = frozenset(
    {
        "baseline_role_query",
        "parallel_via_dataset",
        "direct_query",
    }
)


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


def _identity_values(item: dict[str, Any]) -> tuple[str, ...]:
    metadata = item.get("metadata", {})
    values = [item.get("title"), item.get("locator")]
    if isinstance(metadata, dict):
        values.extend(
            metadata.get(key)
            for key in (
                "doi",
                "arxiv_id",
                "repository_ref",
                "dataset_ref",
                "canonical_url",
            )
        )
    return tuple(value for value in values if isinstance(value, str) and value.strip())


def _strong_dataset_identifiers(value: str) -> set[str]:
    identifiers: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9._-]{2,}", value):
        compact = re.sub(r"[^A-Za-z0-9]+", "", token)
        if (
            any(char.isdigit() for char in compact)
            or token.isupper()
            or (any(char.isupper() for char in token[1:]) and any(char.islower() for char in token))
        ):
            identifiers.add(compact.casefold())
    return identifiers


def _dataset_titles_related(left: str, right: str) -> bool:
    if _titles_related(left, right):
        return True
    return bool(_strong_dataset_identifiers(left) & _strong_dataset_identifiers(right))


def _asset_matches_item(asset: dict[str, Any], item: dict[str, Any]) -> bool:
    title = asset.get("title")
    item_title = item.get("title")
    kind = str(asset.get("kind", ""))
    if isinstance(title, str) and title.strip() and isinstance(item_title, str):
        if kind == "dataset":
            if _dataset_titles_related(title, item_title):
                return True
        elif _titles_related(title, item_title):
            return True
    identity_text = _normalize("\n".join(_identity_values(item)))
    for key in ("doi", "arxiv", "url"):
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            normalized = _normalize(value)
            if normalized and normalized in identity_text:
                return True
    return False


def _is_exact_acronym_alias(alias: str, full_title: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]+", "", alias)
    full_tokens = _normalize(full_title).split()
    return (
        len(compact) >= 3
        and compact.isupper()
        and bool(full_tokens)
        and compact.casefold() == full_tokens[0]
    )


def _titles_related(left: str, right: str) -> bool:
    left_tokens = set(_normalize(left).split())
    right_tokens = set(_normalize(right).split())
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if _is_exact_acronym_alias(left, right) or _is_exact_acronym_alias(right, left):
        return True
    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens
    length_ratio = min(len(left_tokens), len(right_tokens)) / max(
        len(left_tokens), len(right_tokens)
    )
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75


def _state_evidence_items(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = state.get("evidence", {})
    raw_items = evidence.get("items", []) if isinstance(evidence, dict) else []
    return {
        str(item["evidence_id"]): item
        for item in raw_items
        if isinstance(item, dict) and item.get("evidence_id")
    }


def _accepted_verified_items(
    state: dict[str, Any], trace: AcademicTailoringRunTrace
) -> list[dict[str, Any]]:
    items_by_id = _state_evidence_items(state)
    accepted_review_ids = {
        item.evidence_id
        for item in trace.evidence_reviews
        if item.accepted and item.identity_verified and item.relevance_passed
    }
    state_evidence = state.get("evidence", {})
    state_accepted_ids = {
        str(value)
        for value in (
            state_evidence.get("accepted_ids", []) if isinstance(state_evidence, dict) else []
        )
    }
    valid_ids = accepted_review_ids & state_accepted_ids
    return [items_by_id[evidence_id] for evidence_id in valid_ids if evidence_id in items_by_id]


def _retrieval_pipeline_diagnostics(
    state: dict[str, Any], trace: AcademicTailoringRunTrace
) -> dict[str, Any]:
    items_by_id = _state_evidence_items(state)
    candidate_ids = set(items_by_id)
    identity_verified_ids = {
        item.evidence_id for item in trace.evidence_reviews if item.identity_verified
    } & candidate_ids
    relevance_passed_ids = {
        item.evidence_id
        for item in trace.evidence_reviews
        if item.identity_verified and item.relevance_passed
    } & candidate_ids
    trace_accepted_ids = {
        item.evidence_id
        for item in trace.evidence_reviews
        if item.accepted and item.identity_verified and item.relevance_passed
    } & candidate_ids
    state_evidence = state.get("evidence", {})
    state_accepted_ids = {
        str(value)
        for value in (
            state_evidence.get("accepted_ids", []) if isinstance(state_evidence, dict) else []
        )
    } & candidate_ids
    accepted_verified_ids = trace_accepted_ids & state_accepted_ids

    failure_stage: str | None = None
    if not candidate_ids:
        failure_stage = "no_candidates_returned"
    elif not identity_verified_ids:
        failure_stage = "no_identity_verified_candidates"
    elif not relevance_passed_ids:
        failure_stage = "no_relevance_passed_candidates"
    elif not trace_accepted_ids:
        failure_stage = "no_trace_accepted_candidates"
    elif not accepted_verified_ids:
        failure_stage = "state_trace_acceptance_mismatch"

    return {
        "failure_stage": failure_stage,
        "candidate_count": len(candidate_ids),
        "identity_verified_count": len(identity_verified_ids),
        "relevance_passed_count": len(relevance_passed_ids),
        "trace_accepted_count": len(trace_accepted_ids),
        "state_accepted_count": len(state_accepted_ids),
        "accepted_verified_count": len(accepted_verified_ids),
        "identity_rejected_count": len(candidate_ids - identity_verified_ids),
        "relevance_rejected_count": len(identity_verified_ids - relevance_passed_ids),
        "review_rejected_count": len(relevance_passed_ids - trace_accepted_ids),
        "state_trace_mismatch_count": len(trace_accepted_ids ^ state_accepted_ids),
    }


def _accepted_asset_matches(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
    return sum(any(_asset_matches_item(asset, item) for item in items) for asset in assets)


def _dataset_asset_score(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
    if not assets:
        return 7 if items else 0
    total = 0
    for asset in assets:
        matching = [item for item in items if _asset_matches_item(asset, item)]
        if not matching:
            continue
        quality = 0
        for item in matching:
            metadata = item.get("metadata", {})
            relation = metadata.get("relation") if isinstance(metadata, dict) else None
            quality = max(quality, 4 if relation == "dataset_named_in_verified_paper" else 7)
        total += quality
    return round(total / len(assets))


def _declared_baseline_titles(case: dict[str, Any]) -> list[str]:
    supplied = case.get("public_input", {}).get("supplied_materials", [])
    titles: list[str] = []
    for item in supplied:
        if not isinstance(item, dict):
            continue
        role = str(item.get("declared_role", "")).casefold()
        title = item.get("title")
        if "baseline" in role and isinstance(title, str) and title.strip():
            titles.append(title)
    return titles


def _gold_baseline_titles(case: dict[str, Any]) -> list[str]:
    gold = case.get("gold", {})
    titles: list[str] = []
    baseline_decision = gold.get("baseline_decision", {})
    if isinstance(baseline_decision, dict):
        canonical = baseline_decision.get("canonical")
        if isinstance(canonical, str) and canonical.strip():
            titles.append(canonical)
    for item in gold.get("expected_assets", []):
        if not isinstance(item, dict) or item.get("kind") != "paper":
            continue
        role = str(item.get("role", "")).casefold()
        title = item.get("title")
        if "baseline" in role and isinstance(title, str) and title.strip():
            titles.append(title)
    return list(dict.fromkeys(titles))


def _baseline_target_titles(case: dict[str, Any]) -> list[str]:
    declared = _declared_baseline_titles(case)
    return declared if declared else _gold_baseline_titles(case)


def _has_author_linked_repository(
    baseline_source_item: dict[str, Any], accepted_items: list[dict[str, Any]]
) -> bool:
    evidence_id = str(baseline_source_item.get("evidence_id", ""))
    source_paper_id = evidence_id.removeprefix("ev-")
    if not source_paper_id:
        return False
    return any(
        item.get("source_type") == "repository"
        and isinstance(item.get("metadata"), dict)
        and item["metadata"].get("relation") == "author_linked_from_verified_paper"
        and item["metadata"].get("parent_paper_id") == source_paper_id
        for item in accepted_items
    )


def _baseline_identity_status(
    case: dict[str, Any],
    *,
    baseline_name: str | None,
    baseline_source_item: dict[str, Any] | None,
    baseline_targets: list[str],
    accepted_items: list[dict[str, Any]],
) -> str:
    if baseline_name is None:
        return "missing"
    if baseline_source_item is None:
        return "unbound"
    source_title = str(baseline_source_item.get("title", ""))
    if any(
        _titles_related(baseline_name, target) or _titles_related(source_title, target)
        for target in baseline_targets
    ):
        return "exact_target"
    if _declared_baseline_titles(case):
        return "mismatch"
    metadata = baseline_source_item.get("metadata", {})
    relation = metadata.get("relation") if isinstance(metadata, dict) else None
    baseline_candidate = metadata.get("baseline_candidate") if isinstance(metadata, dict) else None
    if case.get("case_type") == "title_only" and baseline_source_item.get("source_type") == "paper":
        if baseline_candidate == "inferred" and relation in _INFERRED_BASELINE_RELATIONS:
            return "evidence_bound_alternative"
        if relation == "direct_query" and _has_author_linked_repository(
            baseline_source_item, accepted_items
        ):
            return "evidence_bound_alternative"
    return "mismatch"


def _specific_protocol_text(value: str | None) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    folded = value.casefold()
    unresolved = (
        "unresolved",
        "not yet",
        "unknown",
        "select and freeze",
        "preserve the documented",
        "待确定",
        "未确定",
        "未知",
    )
    return not any(marker in folded for marker in unresolved)


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
    expected_assets = [item for item in gold.get("expected_assets", []) if isinstance(item, dict)]
    paper_assets = [item for item in expected_assets if item.get("kind") == "paper"]
    repo_assets = [item for item in expected_assets if item.get("kind") == "repository"]
    dataset_assets = [item for item in expected_assets if item.get("kind") == "dataset"]

    accepted_items = _accepted_verified_items(state, trace)
    retrieval_diagnostics = _retrieval_pipeline_diagnostics(state, trace)
    accepted_items_by_id = {
        str(item["evidence_id"]): item for item in accepted_items if item.get("evidence_id")
    }
    accepted_papers = [item for item in accepted_items if item.get("source_type") == "paper"]
    accepted_repos = [item for item in accepted_items if item.get("source_type") == "repository"]
    accepted_datasets = [item for item in accepted_items if item.get("source_type") == "dataset"]
    matched_papers = _accepted_asset_matches(paper_assets, accepted_papers)
    matched_repos = _accepted_asset_matches(repo_assets, accepted_repos)
    matched_datasets = _accepted_asset_matches(dataset_assets, accepted_datasets)

    baseline = trace.baseline
    baseline_targets = _baseline_target_titles(case)
    baseline_source_item = (
        accepted_items_by_id.get(baseline.source_evidence_id)
        if baseline is not None and baseline.source_evidence_id
        else None
    )
    baseline_source_title = (
        str(baseline_source_item.get("title", "")) if baseline_source_item is not None else ""
    )
    baseline_identity_status = _baseline_identity_status(
        case,
        baseline_name=baseline.name if baseline is not None else None,
        baseline_source_item=baseline_source_item,
        baseline_targets=baseline_targets,
        accepted_items=accepted_items,
    )
    baseline_target_match = baseline_identity_status == "exact_target"
    baseline_identity_acceptable = baseline_identity_status in {
        "exact_target",
        "evidence_bound_alternative",
    }

    identity_score = 0
    if accepted_papers:
        identity_score += 5
    if paper_assets:
        identity_score += round(10 * matched_papers / len(paper_assets))
    else:
        identity_score += 10
    if baseline_identity_status == "evidence_bound_alternative":
        identity_score += 5
    identity_score = min(15, identity_score)

    baseline_score = 0
    if baseline is not None and baseline_source_item is not None:
        baseline_score += 5
        if baseline_target_match:
            baseline_score += 5
        elif baseline_identity_status == "evidence_bound_alternative":
            baseline_score += 3
        if baseline.source_evidence_id:
            baseline_score += 2
        if baseline.version_or_commit:
            baseline_score += 3
    baseline_score = min(15, baseline_score)

    dataset_score = _dataset_asset_score(dataset_assets, accepted_datasets)
    if baseline is not None and _specific_protocol_text(baseline.dataset):
        dataset_score += 2
    if baseline is not None and _specific_protocol_text(baseline.split):
        dataset_score += 1
    dataset_score = min(10, dataset_score)

    repository_score = 0
    if repo_assets:
        repository_score += round(7 * matched_repos / len(repo_assets))
    elif accepted_repos:
        repository_score += 7
    if accepted_repos:
        repository_score += 3
    repository_score = min(10, repository_score)

    accepted_review_by_id = {
        item.evidence_id: item for item in trace.evidence_reviews if item.accepted
    }
    gap_evidence_count = sum(
        item.role in {"gap", "negative_result", "risk"} for item in accepted_review_by_id.values()
    )
    gap_score = 0
    if gap_evidence_count:
        gap_score += 4
    if trace.fact_partitions.verified and (
        trace.fact_partitions.inferred or trace.fact_partitions.proposed
    ):
        gap_score += 2
    if len(trace.stop_conditions) >= 2:
        gap_score += 4
    gap_score = min(10, gap_score)

    valid_evidence_ids = set(accepted_items_by_id)
    module_score = 0
    evidence_backed_modules = 0
    if trace.modules:
        module_score += 3
        evidence_backed_modules = sum(
            item.evidence_id in valid_evidence_ids for item in trace.modules
        )
        role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
        module_score += round(4 * evidence_backed_modules / len(trace.modules))
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
        explicitly_compatible_count = sum(item.role_compatible is True for item in trace.modules)
        compatibility_score += round(6 * semantic_count / len(trace.modules))
        compatibility_score += round(2 * switch_count / len(trace.modules))
        compatibility_score += round(4 * explicitly_compatible_count / len(trace.modules))
        compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
    elif trace.module_design_deferred:
        compatibility_score = 3
    compatibility_score = min(15, compatibility_score)

    hypothesis_score = 0
    if _complete_hypothesis(trace):
        hypothesis_score += 3
        if baseline_identity_acceptable and accepted_items:
            hypothesis_score += 2

    experiment_score = 0
    arm_types = {item.arm_type for item in trace.experiments}
    if "baseline" in arm_types:
        experiment_score += 2
    if arm_types & {"full", "single_module", "interaction"}:
        experiment_score += 2
    if "strong_comparison" in arm_types:
        experiment_score += 1
    if any(item.metrics for item in trace.experiments):
        experiment_score += 1
    if any(len(item.seeds) >= 3 or item.uncertainty_reporting for item in trace.experiments):
        experiment_score += 1
    if trace.stop_conditions or any(item.stopping_criteria for item in trace.experiments):
        experiment_score += 1
    if trace.experiments and all(
        _specific_protocol_text(item.dataset) and _specific_protocol_text(item.split)
        for item in trace.experiments
    ):
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
    if not accepted_items:
        hard_failures.append("no_real_retrieval")
    if baseline is not None and baseline_source_item is None:
        hard_failures.append("baseline_not_bound_to_accepted_evidence")
    if baseline_identity_status == "mismatch":
        hard_failures.append("wrong_paper_identity")
    if baseline is None and baseline_targets:
        hard_failures.append("missing_required_baseline")
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
    if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
        hard_failures.append("module_not_bound_to_accepted_evidence")
    if any(
        item.accepted and item.core_evidence and item.role in (None, "other")
        for item in trace.evidence_reviews
    ):
        hard_failures.append("evidence_role_mismatch")
    if trace.decision == "ACCEPT" and (
        hard_failures
        or not baseline_identity_acceptable
        or dataset_score < 5
        or repository_score < 3
    ):
        hard_failures.append("unsupported_acceptance")

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
        "scoring_audit": {
            "accepted_verified_evidence_count": len(accepted_items),
            "accepted_repository_count": len(accepted_repos),
            "accepted_dataset_count": len(accepted_datasets),
            "retrieval_pipeline": retrieval_diagnostics,
            "baseline_name": baseline.name if baseline is not None else None,
            "baseline_source_title": baseline_source_title or None,
            "baseline_targets": baseline_targets,
            "baseline_target_match": baseline_target_match,
            "baseline_identity_status": baseline_identity_status,
            "evidence_bound_alternative_baseline": (
                baseline_identity_status == "evidence_bound_alternative"
            ),
            "evidence_backed_module_count": evidence_backed_modules,
        },
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
    hard_failure_label_count = sum(len(item["hard_failures"]) for item in results)
    hard_failure_case_count = sum(bool(item["hard_failures"]) for item in results)
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
    failed = (
        report["failed"]
        or hard_failure_label_count
        or prompt_findings
        or runtime_summary.get("errors")
    )
    return 1 if args.require_pass and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
