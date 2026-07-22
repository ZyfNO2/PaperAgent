from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperagent.eval_runtime_reporting import (
    RunErrorCategory,
    build_error_record,
    extract_incomplete_context,
    load_resume_checkpoint,
    should_stop_run,
    summarize_errors,
)


def test_structured_error_classifies_provider_budget_and_retryable_failures() -> None:
    authentication = build_error_record(
        case_id="case-1",
        error_code="LLM_AUTHENTICATION",
        message="bad key",
        retryable=False,
        stage="planning",
        call_index=1,
        provider="mistral",
        model="mistral-small-latest",
    )
    budget = build_error_record(
        case_id="case-2",
        error_code="LLM_BUDGET_EXHAUSTED",
        message="budget",
        retryable=False,
    )
    timeout = build_error_record(
        case_id="case-3",
        error_code="LLM_READ_TIMEOUT",
        message="timeout",
        retryable=True,
    )

    assert authentication["error_category"] == RunErrorCategory.FATAL_PROVIDER
    assert budget["error_category"] == RunErrorCategory.FATAL_BUDGET
    assert timeout["error_category"] == RunErrorCategory.RETRYABLE
    assert should_stop_run(str(authentication["error_category"])) is True
    assert should_stop_run(str(timeout["error_category"])) is False


def test_incomplete_context_extracts_trace_and_state_details() -> None:
    context = extract_incomplete_context(
        state={
            "current_node": "method_design",
            "execution": {
                "status": "blocked",
                "repair_attempts": 2,
                "last_error": {
                    "code": "LLM_SCHEMA_VALIDATION",
                    "message": "invalid JSON",
                    "node": "method_design",
                    "retryable": False,
                    "details": {"call_index": 8},
                },
            },
        },
        trace={"module_defer_reason": "LLM_RESPONSE_SCHEMA_INVALID"},
    )

    assert context["stage"] == "method_design"
    assert context["call_index"] == 8
    assert context["repair_attempts"] == 2
    assert context["execution_status"] == "blocked"
    assert context["message"] == "invalid JSON"


def test_error_summary_records_first_fatal_and_provider_counts() -> None:
    errors = [
        build_error_record(
            case_id="case-1",
            error_code="LLM_SCHEMA_VALIDATION",
            message="case error",
            retryable=False,
            provider="nvidia",
        ),
        build_error_record(
            case_id="case-2",
            error_code="LLM_AUTHENTICATION",
            message="fatal",
            retryable=False,
            provider="mistral",
            budget_consumed_usd=0.02,
        ),
    ]
    summary = summarize_errors(errors, attempted_case_ids=["case-1", "case-2"])

    assert summary["total_errors"] == 2
    assert summary["fatal_errors"] == 1
    assert summary["first_fatal_at"]["case_index"] == 2
    assert summary["by_provider"]["mistral"]["FATAL_PROVIDER"] == 1


def test_resume_checkpoint_requires_complete_prefix_and_matching_digest(
    tmp_path: Path,
) -> None:
    selected = ["case-1", "case-2", "case-3"]
    (tmp_path / "execution-summary.json").write_text(
        json.dumps(
            {
                "public_dataset_sha256": "a" * 64,
                "errors": [
                    {
                        "case_id": "case-2",
                        "error_category": "CASE_ERROR",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "states.jsonl").write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "state": {"execution": {"status": "completed"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "run-traces.jsonl").write_text(
        json.dumps({"case_id": "case-1"}) + "\n",
        encoding="utf-8",
    )

    states, traces, errors, completed = load_resume_checkpoint(
        output_dir=tmp_path,
        resume_from_case_id="case-2",
        selected_case_ids=selected,
        expected_public_sha256="a" * 64,
    )
    assert len(states) == len(traces) == 1
    assert errors == []
    assert completed == ["case-1"]

    with pytest.raises(ValueError, match="digest"):
        load_resume_checkpoint(
            output_dir=tmp_path,
            resume_from_case_id="case-2",
            selected_case_ids=selected,
            expected_public_sha256="b" * 64,
        )
