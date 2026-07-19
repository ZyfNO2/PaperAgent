from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from paperagent.claw_academic_benchmark import (
    SOURCE_COMMIT,
    AcademicTailoringRunTrace,
    AggregateEvaluation,
    EvidenceReview,
    build_gold_self_check_trace,
    evaluate_case,
    evaluate_dataset,
    load_gold_dataset,
    run_gold_self_check,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "evals" / "claw_academic_tailoring_v1"


def _trace_with(
    trace: AcademicTailoringRunTrace,
    **updates: object,
) -> AcademicTailoringRunTrace:
    payload = trace.model_dump(mode="json", by_alias=True)
    payload.update(updates)
    return AcademicTailoringRunTrace.model_validate(payload)


def test_imported_snapshot_is_exact_and_structurally_valid() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    assert dataset.source.source_commit == SOURCE_COMMIT
    assert dataset.source.mode == "read_only_snapshot"
    assert len(dataset.cases) == 20
    assert len(dataset.dataset_digest) == 64
    assert [len(case.supplied_materials) for case in dataset.cases].count(0) == 15
    assert [len(case.supplied_materials) for case in dataset.cases].count(1) == 3
    assert [len(case.supplied_materials) for case in dataset.cases].count(2) == 2


def test_snapshot_loader_rejects_local_data_drift(tmp_path: Path) -> None:
    copied = tmp_path / "snapshot"
    shutil.copytree(DATASET_ROOT, copied)
    shard = copied / "cases-01.jsonl"
    shard.write_text(shard.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="diverges from PaperClaw blob"):
        load_gold_dataset(copied)


def test_gold_evaluator_self_check_passes_all_twenty_cases() -> None:
    report = run_gold_self_check(DATASET_ROOT)
    assert report.total == 20
    assert report.passed == 20
    assert report.failed == 0
    assert report.average_score == 100.0
    assert report.decision_accuracy == 1.0
    assert report.hard_failure_count == 0
    assert all(result.score == 100 for result in report.cases)
    assert all(result.status == "passed" for result in report.cases)


def test_report_digest_and_derived_counts_are_fail_closed() -> None:
    report = run_gold_self_check(DATASET_ROOT)
    payload = report.model_dump(mode="json", by_alias=True)
    payload["passed"] = 19
    with pytest.raises(ValueError, match="aggregate passed count"):
        AggregateEvaluation.model_validate(payload)

    payload = report.model_dump(mode="json", by_alias=True)
    payload["report_digest"] = "0" * 64
    with pytest.raises(ValueError, match="report digest mismatch"):
        AggregateEvaluation.model_validate(payload)


def test_identity_verified_but_relevance_failed_cannot_be_accepted() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    case = next(item for item in dataset.cases if item.case_id == "at-018-yolox-tinydet-supplied")
    trace = build_gold_self_check_trace(case)
    reviews = list(trace.evidence_reviews)
    first = reviews[0]
    reviews[0] = EvidenceReview.model_validate(
        {
            **first.model_dump(mode="json"),
            "relevance_passed": False,
            "accepted": True,
        }
    )
    mutated = _trace_with(
        trace,
        evidence_reviews=[item.model_dump(mode="json") for item in reviews],
    )
    result = evaluate_case(case, mutated)
    assert result.status == "failed"
    assert "IDENTITY_ONLY_ACCEPTANCE" in {item.code for item in result.hard_failures}
    relevance_stage = next(item for item in result.stages if item.stage == "relevance_review")
    assert not relevance_stage.passed


def test_incompatible_supplied_paper_is_a_hard_failure() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    case = next(
        item for item in dataset.cases if item.case_id == "at-020-lightgcn-contrastive-supplied"
    )
    trace = build_gold_self_check_trace(case)
    reviews = list(trace.evidence_reviews)
    supplied = reviews[1]
    reviews[1] = EvidenceReview.model_validate(
        {
            **supplied.model_dump(mode="json"),
            "role_compatible": False,
        }
    )
    mutated = _trace_with(
        trace,
        evidence_reviews=[item.model_dump(mode="json") for item in reviews],
    )
    result = evaluate_case(case, mutated)
    assert result.status == "failed"
    assert "FORCED_INCOMPATIBLE_SUPPLIED_MATERIAL" in {item.code for item in result.hard_failures}


def test_revise_pilot_mapping_is_explicit_and_not_implicit() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    case = dataset.cases[0]
    trace = build_gold_self_check_trace(case)
    assert trace.decision == "REVISE"
    assert trace.pilot_recommended
    assert evaluate_case(case, trace).decision_matches

    without_pilot = _trace_with(trace, pilot_recommended=False)
    result = evaluate_case(case, without_pilot)
    assert result.observed_decision == "REVISE"
    assert not result.decision_matches
    assert result.status == "failed"


def test_fabrication_and_trace_contract_failure_are_blocking() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    case = dataset.cases[0]
    trace = build_gold_self_check_trace(case)
    mutated = _trace_with(
        trace,
        fabricated_items=["doi:10.0000/fabricated"],
        trace_audit_passed=False,
        trace_error_codes=["UNKNOWN_REPORT_EVIDENCE"],
    )
    result = evaluate_case(case, mutated)
    assert result.status == "failed"
    assert {item.code for item in result.hard_failures} == {
        "FABRICATED_ITEM",
        "TRACE_CONTRACT_FAILURE",
    }


def test_dataset_evaluation_requires_exact_case_identity() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    traces = tuple(build_gold_self_check_trace(case) for case in dataset.cases[:-1])
    with pytest.raises(ValueError, match="case identity mismatch"):
        evaluate_dataset(dataset, traces)


def test_jsonl_run_contract_round_trips() -> None:
    dataset = load_gold_dataset(DATASET_ROOT)
    traces = tuple(build_gold_self_check_trace(case) for case in dataset.cases)
    serialized = "\n".join(item.model_dump_json(by_alias=True) for item in traces)
    restored = tuple(
        AcademicTailoringRunTrace.model_validate_json(line) for line in serialized.splitlines()
    )
    report = evaluate_dataset(dataset, restored)
    decoded = json.loads(report.model_dump_json(by_alias=True))
    assert decoded["source_commit"] == SOURCE_COMMIT
    assert decoded["passed"] == 20
