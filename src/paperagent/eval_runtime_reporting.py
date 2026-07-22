from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class RunErrorCategory(StrEnum):
    FATAL_PROVIDER = "FATAL_PROVIDER"
    FATAL_BUDGET = "FATAL_BUDGET"
    CASE_ERROR = "CASE_ERROR"
    RETRYABLE = "RETRYABLE"


_FATAL_PROVIDER_CODES = frozenset(
    {
        "LLM_CONFIGURATION",
        "LLM_AUTHENTICATION",
        "LLM_PERMISSION",
        "LLM_INVALID_REQUEST",
        "LLM_RESPONSE_FORMAT_UNSUPPORTED",
    }
)
_FATAL_BUDGET_CODES = frozenset(
    {
        "GLOBAL_BUDGET_EXHAUSTED",
        "PROVIDER_CALL_BUDGET_EXHAUSTED",
        "RUN_BUDGET_EXHAUSTED",
    }
)
_RETRYABLE_CODES = frozenset(
    {
        "LLM_CONNECT",
        "LLM_PROVIDER_5XX",
        "LLM_RATE_LIMITED",
        "LLM_READ_TIMEOUT",
        "LLM_TIMEOUT",
        "PROVIDER_TIMEOUT",
    }
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_public_dataset_digest(dataset: Mapping[str, Any]) -> str:
    declared = dataset.get("public_sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise ValueError("public dataset must contain a 64-character public_sha256")
    payload = dict(dataset)
    payload.pop("public_sha256", None)
    actual = canonical_sha256(payload)
    if actual != declared:
        raise ValueError(
            f"public dataset digest mismatch: declared={declared!r}, actual={actual!r}"
        )
    return actual


def normalize_error_code(value: object, *, fallback: str = "CASE_EXECUTION_INCOMPLETE") -> str:
    if value is None:
        return fallback
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        return fallback
    normalized = raw.strip().upper().replace("-", "_")
    if not normalized:
        return fallback
    if normalized.startswith("LLM_") or normalized.startswith("MAX_"):
        return normalized
    provider_names = {
        "AUTHENTICATION",
        "BUDGET_EXHAUSTED",
        "CANCELLED",
        "CONFIGURATION",
        "CONNECT",
        "INVALID_REQUEST",
        "MALFORMED_RESPONSE",
        "PERMISSION",
        "PROVIDER_5XX",
        "RATE_LIMITED",
        "READ_TIMEOUT",
        "SCHEMA_VALIDATION",
        "UNKNOWN",
        "UNSUPPORTED_SCHEMA",
    }
    if normalized in provider_names:
        return f"LLM_{normalized}"
    return normalized


def classify_error(*, error_code: str, retryable: bool) -> RunErrorCategory:
    if error_code in _FATAL_PROVIDER_CODES:
        return RunErrorCategory.FATAL_PROVIDER
    if error_code in _FATAL_BUDGET_CODES:
        return RunErrorCategory.FATAL_BUDGET
    if retryable or error_code in _RETRYABLE_CODES:
        return RunErrorCategory.RETRYABLE
    return RunErrorCategory.CASE_ERROR


def should_stop_run(category: RunErrorCategory | str) -> bool:
    normalized = RunErrorCategory(category)
    return normalized in {
        RunErrorCategory.FATAL_PROVIDER,
        RunErrorCategory.FATAL_BUDGET,
    }


def stage_from_task(task: object) -> str:
    if not isinstance(task, str) or not task.strip():
        return "unknown"
    normalized = task.strip().casefold()
    if "plan" in normalized or "intake" in normalized:
        return "planning"
    if "retriev" in normalized or "search" in normalized:
        return "retrieval"
    if "evidence" in normalized or "synth" in normalized:
        return "synthesis"
    if "method" in normalized or "compat" in normalized:
        return "method_design"
    if "quality" in normalized or "gate" in normalized:
        return "quality_gate"
    if "report" in normalized:
        return "report"
    return normalized.replace(" ", "_")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_non_empty(*values: object) -> object | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def extract_incomplete_context(
    *,
    state: Mapping[str, Any],
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    execution = _mapping(state.get("execution"))
    last_error = _mapping(execution.get("last_error"))
    details = _mapping(last_error.get("details"))
    trace_codes = trace.get("trace_error_codes")
    last_trace_code = trace_codes[-1] if isinstance(trace_codes, list) and trace_codes else None
    error_code = normalize_error_code(
        _first_non_empty(
            last_error.get("code"),
            trace.get("module_defer_reason"),
            last_trace_code,
        )
    )
    task = _first_non_empty(
        last_error.get("node"),
        state.get("current_node"),
        trace.get("current_node"),
        trace.get("last_completed_node"),
    )
    return {
        "error_code": error_code,
        "stage": stage_from_task(task),
        "node": task if isinstance(task, str) else None,
        "call_index": _first_non_empty(details.get("call_index"), trace.get("call_index")),
        "retryable": bool(last_error.get("retryable", False)),
        "repair_attempts": int(
            _first_non_empty(
                trace.get("method_repair_count"),
                trace.get("repair_attempts"),
                execution.get("repair_attempts"),
                0,
            )
            or 0
        ),
        "execution_status": execution.get("status"),
        "message": _first_non_empty(
            last_error.get("message"),
            f"execution status was {execution.get('status')!r}",
        ),
    }


def build_error_record(
    *,
    case_id: str,
    error_code: object,
    message: str,
    retryable: bool,
    stage: str = "unknown",
    node: str | None = None,
    call_index: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    endpoint_id: str | None = None,
    error_type: str | None = None,
    repair_attempts: int = 0,
    execution_status: str | None = None,
    budget_consumed_usd: float | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    normalized_code = normalize_error_code(error_code)
    category = classify_error(error_code=normalized_code, retryable=retryable)
    return {
        "case_id": case_id,
        "stage": stage,
        "node": node,
        "call_index": call_index,
        "provider": provider,
        "model": model,
        "endpoint_id": endpoint_id,
        "error_code": normalized_code,
        "error_category": category.value,
        "error_type": error_type,
        "message": message,
        "retryable": retryable,
        "repair_attempts": repair_attempts,
        "execution_status": execution_status,
        "budget_consumed_usd": budget_consumed_usd,
        "timestamp": timestamp or utc_now_iso(),
    }


def summarize_errors(
    errors: Sequence[Mapping[str, Any]],
    *,
    attempted_case_ids: Sequence[str],
) -> dict[str, Any]:
    category_counts = Counter(str(error.get("error_category") or "UNKNOWN") for error in errors)
    provider_counts: dict[str, Counter[str]] = defaultdict(Counter)
    first_fatal: dict[str, Any] | None = None
    consumed_before_fatal = 0.0
    attempted_index = {case_id: index for index, case_id in enumerate(attempted_case_ids, start=1)}

    for error in errors:
        provider = str(error.get("provider") or "unknown")
        category = str(error.get("error_category") or "UNKNOWN")
        provider_counts[provider][category] += 1
        amount = error.get("budget_consumed_usd")
        if isinstance(amount, int | float):
            consumed_before_fatal += float(amount)
        if first_fatal is None and category in {
            RunErrorCategory.FATAL_PROVIDER.value,
            RunErrorCategory.FATAL_BUDGET.value,
        }:
            case_id = str(error.get("case_id") or "")
            first_fatal = {
                "case_id": case_id,
                "case_index": attempted_index.get(case_id),
                "error_code": error.get("error_code"),
                "error_category": category,
            }

    return {
        "total_errors": len(errors),
        "fatal_errors": sum(
            category_counts.get(category.value, 0)
            for category in (RunErrorCategory.FATAL_PROVIDER, RunErrorCategory.FATAL_BUDGET)
        ),
        "case_errors": category_counts.get(RunErrorCategory.CASE_ERROR.value, 0),
        "retryable_errors": category_counts.get(RunErrorCategory.RETRYABLE.value, 0),
        "by_provider": {
            provider: dict(sorted(counts.items()))
            for provider, counts in sorted(provider_counts.items())
        },
        "by_category": dict(sorted(category_counts.items())),
        "first_fatal_at": first_fatal,
        "budget_consumed_before_fatal_usd": round(consumed_before_fatal, 9),
    }


def load_resume_checkpoint(
    *,
    output_dir: Path,
    resume_from_case_id: str,
    selected_case_ids: Sequence[str],
    expected_public_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if resume_from_case_id not in selected_case_ids:
        raise ValueError(f"unknown --resume-from case ID: {resume_from_case_id}")
    summary_path = output_dir / "execution-summary.json"
    states_path = output_dir / "states.jsonl"
    traces_path = output_dir / "run-traces.jsonl"
    if not all(path.is_file() for path in (summary_path, states_path, traces_path)):
        raise ValueError(
            "resume requires execution-summary.json, states.jsonl, and run-traces.jsonl"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("public_dataset_sha256") != expected_public_sha256:
        raise ValueError("resume checkpoint public dataset digest does not match current dataset")

    resume_index = selected_case_ids.index(resume_from_case_id)
    required_prefix = set(selected_case_ids[:resume_index])
    raw_states = [
        json.loads(line)
        for line in states_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    completed_states: list[dict[str, Any]] = []
    completed_ids: list[str] = []
    for item in raw_states:
        case_id = str(item.get("case_id") or "")
        execution = _mapping(_mapping(item.get("state")).get("execution"))
        if case_id in required_prefix and execution.get("status") == "completed":
            completed_states.append(item)
            completed_ids.append(case_id)
    if set(completed_ids) != required_prefix:
        missing = sorted(required_prefix - set(completed_ids))
        raise ValueError(f"resume checkpoint is missing completed prefix cases: {missing}")

    raw_traces = [
        json.loads(line)
        for line in traces_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    completed_traces = [
        trace for trace in raw_traces if str(trace.get("case_id") or "") in required_prefix
    ]
    existing_errors = [
        dict(error)
        for error in summary.get("errors", [])
        if isinstance(error, Mapping) and str(error.get("case_id") or "") in required_prefix
    ]
    return completed_states, completed_traces, existing_errors, completed_ids
