from __future__ import annotations

from pathlib import Path


SCORER_PATH = Path("scripts/score_academic_tailoring_retrieval_v1.py")
INTAKE_TEST_PATH = Path("tests/nodes/test_intake_planning.py")
SCORER_TEST_PATH = Path("tests/evals/test_academic_tailoring_retrieval_v1_scorer.py")


HELPERS = r'''

def _titles_related(left: str, right: str) -> bool:
    left_normalized = _normalize(left)
    right_normalized = _normalize(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return True
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    smaller = min(len(left_tokens), len(right_tokens))
    if smaller < 3:
        return False
    overlap = len(left_tokens & right_tokens)
    return overlap / smaller >= 0.8


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


def _accepted_asset_matches(
    assets: list[dict[str, Any]], items: list[dict[str, Any]]
) -> int:
    accepted_text = _normalize("\n".join(_flatten_strings(items)))
    return sum(_asset_matches(asset, accepted_text) for asset in assets)


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
'''


STRICT_SCORE_CASE = r'''def _score_case(
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
    baseline_target_match = bool(
        baseline is not None
        and baseline_targets
        and any(
            _titles_related(baseline.name, target)
            or _titles_related(baseline_source_title, target)
            for target in baseline_targets
        )
    )

    identity_score = 0
    if accepted_papers:
        identity_score += 5
    if paper_assets:
        identity_score += round(10 * matched_papers / len(paper_assets))
    else:
        identity_score += 10
    identity_score = min(15, identity_score)

    baseline_score = 0
    if baseline is not None and baseline_source_item is not None:
        baseline_score += 5
        if baseline_target_match:
            baseline_score += 5
        if baseline.source_evidence_id:
            baseline_score += 2
        if baseline.version_or_commit:
            baseline_score += 3
    baseline_score = min(15, baseline_score)

    dataset_score = 0
    if dataset_assets:
        dataset_score += round(7 * matched_datasets / len(dataset_assets))
    elif accepted_datasets:
        dataset_score += 7
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

    accepted_review_by_id = {item.evidence_id: item for item in trace.evidence_reviews if item.accepted}
    gap_evidence_count = sum(
        item.role in {"gap", "negative_result", "risk"}
        for item in accepted_review_by_id.values()
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
        evidence_backed_modules = sum(item.evidence_id in valid_evidence_ids for item in trace.modules)
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
        if baseline_target_match and accepted_items:
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
    if baseline is not None and baseline_targets and not baseline_target_match:
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
        hard_failures or not baseline_target_match or dataset_score < 5 or repository_score < 3
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
            "baseline_name": baseline.name if baseline is not None else None,
            "baseline_source_title": baseline_source_title or None,
            "baseline_targets": baseline_targets,
            "baseline_target_match": baseline_target_match,
            "evidence_backed_module_count": evidence_backed_modules,
        },
    }
'''


TEST_CONTENT = r'''from __future__ import annotations

from types import SimpleNamespace

from scripts.score_academic_tailoring_retrieval_v1 import (
    _accepted_verified_items,
    _baseline_target_titles,
    _titles_related,
)


def test_titles_related_accepts_alias_containment_but_rejects_neighbor_paper() -> None:
    assert _titles_related("USAD", "USAD: UnSupervised Anomaly Detection on Multivariate Time Series")
    assert not _titles_related(
        "TimeMachine: A Time Series is Worth 4 Mambas for Long-Term Forecasting",
        "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers",
    )
    assert not _titles_related(
        "BEiT: BERT Pre-Training of Image Transformers",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    )


def test_declared_baseline_titles_override_gold_alternatives() -> None:
    case = {
        "public_input": {
            "supplied_materials": [
                {"title": "Oriented R-CNN", "declared_role": "reproduced baseline"},
                {"title": "Parallel Paper", "declared_role": "parallel paper"},
            ]
        },
        "gold": {
            "baseline_decision": {"canonical": "Another Baseline"},
            "expected_assets": [],
        },
    }
    assert _baseline_target_titles(case) == ["Oriented R-CNN"]


def test_only_accepted_verified_relevant_evidence_can_score() -> None:
    state = {
        "evidence": {
            "accepted_ids": ["good", "rejected-review"],
            "items": [
                {"evidence_id": "good", "title": "Correct Paper", "source_type": "paper"},
                {
                    "evidence_id": "rejected-review",
                    "title": "Correct Repository",
                    "source_type": "repository",
                },
                {"evidence_id": "not-accepted", "title": "Gold Paper", "source_type": "paper"},
            ],
        }
    }
    reviews = [
        SimpleNamespace(
            evidence_id="good", accepted=True, identity_verified=True, relevance_passed=True
        ),
        SimpleNamespace(
            evidence_id="rejected-review",
            accepted=False,
            identity_verified=True,
            relevance_passed=True,
        ),
        SimpleNamespace(
            evidence_id="not-accepted",
            accepted=True,
            identity_verified=True,
            relevance_passed=True,
        ),
    ]
    trace = SimpleNamespace(evidence_reviews=reviews)

    items = _accepted_verified_items(state, trace)

    assert [item["evidence_id"] for item in items] == ["good"]
'''


def main() -> int:
    source = SCORER_PATH.read_text(encoding="utf-8")
    if "def _titles_related(" not in source:
        marker = "\n\ndef _gold_only_phrases(case: dict[str, Any]) -> list[str]:\n"
        if marker not in source:
            raise RuntimeError("scorer helper insertion marker not found")
        source = source.replace(marker, HELPERS + marker, 1)

    start = source.find("def _score_case(")
    end = source.find("\n\ndef _parser()", start)
    if start < 0 or end < 0:
        raise RuntimeError("score case block not found")
    source = source[:start] + STRICT_SCORE_CASE + source[end:]
    SCORER_PATH.write_text(source, encoding="utf-8")

    intake_tests = INTAKE_TEST_PATH.read_text(encoding="utf-8")
    old = '''    assert normalized.search_queries[0].source_types == [
        "paper",
        "repository",
        "web",
    ]
'''
    new = '''    assert normalized.search_queries[0].source_types == [
        "paper",
        "repository",
        "dataset",
        "web",
    ]
'''
    if old in intake_tests:
        intake_tests = intake_tests.replace(old, new, 1)
    elif new not in intake_tests:
        raise RuntimeError("legacy source type assertion not found")
    INTAKE_TEST_PATH.write_text(intake_tests, encoding="utf-8")

    if not SCORER_TEST_PATH.exists():
        SCORER_TEST_PATH.write_text(TEST_CONTENT, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
