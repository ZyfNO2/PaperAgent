from __future__ import annotations

from pathlib import Path

PATH = Path("scripts/run_academic_tailoring_retrieval_v1.py")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, found {count}: {old[:120]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        """import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, TypeVar
""",
        """import argparse
import asyncio
import json
import os
from pathlib import Path
from time import monotonic
from typing import Any, TypeVar
""",
    )
    text = replace_once(
        text,
        """from paperagent.benchmark_input import BenchmarkInput
""",
        """from paperagent.benchmark_input import BenchmarkInput
from paperagent.eval_runtime_reporting import (
    build_error_record,
    extract_incomplete_context,
    load_resume_checkpoint,
    should_stop_run,
    stage_from_task,
    summarize_errors,
    utc_now_iso,
    validate_public_dataset_digest,
)
""",
    )
    text = replace_once(
        text,
        """    errors: list[dict[str, str]],
""",
        """    errors: list[dict[str, object]],
""",
    )
    text = replace_once(
        text,
        """    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("public dataset must contain cases")
    return raw
""",
        """    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("public dataset must contain cases")
    validate_public_dataset_digest(raw)
    return raw
""",
    )
    text = replace_once(
        text,
        """class AuditedLLMProvider:
    def __init__(self, delegate: LLMProvider, *, prompt_log: Path, case_id: str) -> None:
        self._delegate = delegate
        self._prompt_log = prompt_log
        self._case_id = case_id

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)
""",
        """class AuditedLLMProvider:
    def __init__(
        self,
        delegate: LLMProvider,
        *,
        prompt_log: Path,
        case_id: str,
        provider_metadata: dict[str, object],
    ) -> None:
        self._delegate = delegate
        self._prompt_log = prompt_log
        self._case_id = case_id
        self._provider_metadata = dict(provider_metadata)
        self._last_call_context: dict[str, object] = {}

    @property
    def last_call_context(self) -> dict[str, object]:
        return dict(self._last_call_context)

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)
""",
    )
    text = replace_once(
        text,
        """    ) -> T:
        _append_jsonl(
""",
        """    ) -> T:
        self._last_call_context = {
            "task": task,
            "stage": stage_from_task(task),
            "call_index": call_index,
            "provider": self._provider_metadata.get("provider"),
            "model": self._provider_metadata.get("model"),
            "endpoint_id": self._provider_metadata.get("endpoint_id"),
        }
        _append_jsonl(
""",
    )
    text = replace_once(
        text,
        """    parser.add_argument("--allow-gold-in-workspace", action="store_true")
    return parser
""",
        """    parser.add_argument("--allow-gold-in-workspace", action="store_true")
    parser.add_argument(
        "--source-commit",
        default=None,
        help="Full 40-character commit SHA for the executed source tree.",
    )
    parser.add_argument(
        "--resume-from",
        default=None,
        help="Resume from this case ID using the checkpoint in --output-dir.",
    )
    return parser
""",
    )
    text = replace_once(
        text,
        """async def _run(args: argparse.Namespace) -> int:
    if not args.allow_gold_in_workspace:
""",
        """async def _run(args: argparse.Namespace) -> int:
    run_started_at = utc_now_iso()
    run_started_monotonic = monotonic()
    if not args.allow_gold_in_workspace:
""",
    )
    text = replace_once(
        text,
        """    dataset = _load_public_dataset(args.dataset)
    cases = list(dataset["cases"])
""",
        """    dataset = _load_public_dataset(args.dataset)
    source_sha = args.source_commit or os.getenv("PAPERAGENT_SOURCE_SHA") or os.getenv("GITHUB_SHA")
    if not isinstance(source_sha, str) or len(source_sha.strip()) != 40:
        raise ValueError(
            "a full source commit is required via --source-commit, "
            "PAPERAGENT_SOURCE_SHA, or GITHUB_SHA"
        )
    source_sha = source_sha.strip().lower()
    if any(character not in "0123456789abcdef" for character in source_sha):
        raise ValueError("source commit must be a 40-character hexadecimal SHA")
    cases = list(dataset["cases"])
""",
    )
    text = replace_once(
        text,
        """    prompt_log = output_dir / "prompt-log.jsonl"
    prompt_log.parent.mkdir(parents=True, exist_ok=True)
    prompt_log.write_text("", encoding="utf-8")
""",
        """    prompt_log = output_dir / "prompt-log.jsonl"
    prompt_log.parent.mkdir(parents=True, exist_ok=True)
    if args.resume_from is None:
        prompt_log.write_text("", encoding="utf-8")
    else:
        prompt_log.touch(exist_ok=True)
""",
    )
    text = replace_once(
        text,
        """    states: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    attempted_case_ids: list[str] = []
    completed_case_count = 0
    fatal_provider_error: dict[str, str] | None = None
""",
        """    states: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    attempted_case_ids: list[str] = []
    completed_case_count = 0
    fatal_provider_error: dict[str, str] | None = None
    resume_start_index = 0
    if args.resume_from is not None:
        selected_case_ids = [str(case["case_id"]) for case in cases]
        states, traces, errors, completed_case_ids = load_resume_checkpoint(
            output_dir=output_dir,
            resume_from_case_id=args.resume_from,
            selected_case_ids=selected_case_ids,
            expected_public_sha256=str(dataset["public_sha256"]),
        )
        attempted_case_ids = list(completed_case_ids)
        completed_case_count = len(completed_case_ids)
        resume_start_index = selected_case_ids.index(args.resume_from)
""",
    )
    text = replace_once(
        text,
        """        _write_runtime_outputs(
            output_dir=output_dir,
            states=states,
            traces=traces,
            summary=summary,
        )
        return summary
""",
        """        completed_at = utc_now_iso()
        summary.update(
            {
                "source_sha": source_sha,
                "started_at": run_started_at,
                "completed_at": completed_at,
                "duration_seconds": max(monotonic() - run_started_monotonic, 0.000001),
                "runtime_errors": len(errors),
                "run_status": (
                    "completed"
                    if completed_case_count == len(cases) and not errors
                    else "partial"
                ),
                "scientific_acceptance": False,
                "error_summary": summarize_errors(
                    errors,
                    attempted_case_ids=attempted_case_ids,
                ),
            }
        )
        _write_runtime_outputs(
            output_dir=output_dir,
            states=states,
            traces=traces,
            summary=summary,
        )
        return summary
""",
    )
    text = replace_once(
        text,
        """    for index, (case, search_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
        case_id = str(case["case_id"])
        attempted_case_ids.append(case_id)
""",
        """    for index, (case, search_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
        if args.resume_from is not None and index <= resume_start_index:
            continue
        case_id = str(case["case_id"])
        attempted_case_ids.append(case_id)
""",
    )
    text = replace_once(
        text,
        """        try:
            llm = AuditedLLMProvider(
                build_llm_provider(case_provider_config, price_table),
                prompt_log=prompt_log,
                case_id=case_id,
            )
""",
        """        llm: AuditedLLMProvider | None = None
        try:
            llm = AuditedLLMProvider(
                build_llm_provider(case_provider_config, price_table),
                prompt_log=prompt_log,
                case_id=case_id,
                provider_metadata=safe_provider_config,
            )
""",
    )
    text = replace_once(
        text,
        """            fatal_code = _fatal_provider_error_code_from_trace(trace_payload)
            if fatal_code is not None:
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": fatal_code,
                    "message": "fatal LLM provider failure surfaced in the case trace",
                }
                errors.append(
                    {
                        "case_id": case_id,
                        "error_type": "FatalLLMProviderError",
                        "message": fatal_code,
                    }
                )
                break
            execution = state.get("execution")
            execution_status = execution.get("status") if isinstance(execution, dict) else None
            if execution_status != "completed":
                errors.append(
                    {
                        "case_id": case_id,
                        "error_type": "CaseExecutionIncomplete",
                        "message": f"execution status was {execution_status!r}",
                    }
                )
                continue
""",
        """            fatal_code = _fatal_provider_error_code_from_trace(trace_payload)
            if fatal_code is not None:
                context = extract_incomplete_context(state=state, trace=trace_payload)
                error = build_error_record(
                    case_id=case_id,
                    error_code=fatal_code,
                    message="fatal LLM provider failure surfaced in the case trace",
                    retryable=False,
                    stage=str(context["stage"]),
                    node=context.get("node"),
                    call_index=context.get("call_index"),
                    provider=str(safe_provider_config.get("provider") or "unknown"),
                    model=str(safe_provider_config.get("model") or "unknown"),
                    endpoint_id=str(safe_provider_config.get("endpoint_id") or "") or None,
                    error_type="FatalLLMProviderError",
                    repair_attempts=int(context["repair_attempts"]),
                    execution_status=context.get("execution_status"),
                )
                errors.append(error)
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": str(error["error_code"]),
                    "message": str(error["message"]),
                }
                if should_stop_run(str(error["error_category"])):
                    break
            execution = state.get("execution")
            execution_status = execution.get("status") if isinstance(execution, dict) else None
            if execution_status != "completed":
                context = extract_incomplete_context(state=state, trace=trace_payload)
                error = build_error_record(
                    case_id=case_id,
                    error_code=context["error_code"],
                    message=str(context["message"]),
                    retryable=bool(context["retryable"]),
                    stage=str(context["stage"]),
                    node=context.get("node"),
                    call_index=context.get("call_index"),
                    provider=str(safe_provider_config.get("provider") or "unknown"),
                    model=str(safe_provider_config.get("model") or "unknown"),
                    endpoint_id=str(safe_provider_config.get("endpoint_id") or "") or None,
                    error_type="CaseExecutionIncomplete",
                    repair_attempts=int(context["repair_attempts"]),
                    execution_status=context.get("execution_status"),
                )
                errors.append(error)
                if should_stop_run(str(error["error_category"])):
                    fatal_provider_error = {
                        "case_id": case_id,
                        "code": str(error["error_code"]),
                        "message": str(error["message"]),
                    }
                    break
                continue
""",
    )
    text = replace_once(
        text,
        """        except ProviderError as exc:
            normalized = _normalize_provider_error_code(exc.error_code) or exc.code
            errors.append(
                {
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            if normalized in _FATAL_PROVIDER_ERROR_CODES:
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": normalized,
                    "message": "fatal LLM provider failure raised before case completion",
                }
                break
        except Exception as exc:
            normalized = _normalize_provider_error_code(getattr(exc, "code", None))
            errors.append(
                {
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            if normalized in _FATAL_PROVIDER_ERROR_CODES:
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": normalized,
                    "message": "fatal LLM provider failure raised before case completion",
                }
                break
""",
        """        except ProviderError as exc:
            normalized = _normalize_provider_error_code(exc.error_code) or exc.code
            context = llm.last_call_context if llm is not None else {}
            error = build_error_record(
                case_id=case_id,
                error_code=normalized,
                message=str(exc),
                retryable=bool(getattr(exc, "retryable", False)),
                stage=str(context.get("stage") or stage_from_task(getattr(exc, "task", None))),
                node=str(getattr(exc, "task", "")) or None,
                call_index=context.get("call_index"),
                provider=str(context.get("provider") or safe_provider_config.get("provider") or "unknown"),
                model=str(context.get("model") or safe_provider_config.get("model") or "unknown"),
                endpoint_id=str(context.get("endpoint_id") or "") or None,
                error_type=type(exc).__name__,
            )
            errors.append(error)
            if should_stop_run(str(error["error_category"])):
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": str(error["error_code"]),
                    "message": str(error["message"]),
                }
                break
        except Exception as exc:
            normalized = _normalize_provider_error_code(getattr(exc, "code", None))
            context = llm.last_call_context if llm is not None else {}
            error = build_error_record(
                case_id=case_id,
                error_code=normalized or "CASE_RUNNER_EXCEPTION",
                message=str(exc),
                retryable=bool(getattr(exc, "retryable", False)),
                stage=str(context.get("stage") or "unknown"),
                call_index=context.get("call_index"),
                provider=str(context.get("provider") or safe_provider_config.get("provider") or "unknown"),
                model=str(context.get("model") or safe_provider_config.get("model") or "unknown"),
                endpoint_id=str(context.get("endpoint_id") or "") or None,
                error_type=type(exc).__name__,
            )
            errors.append(error)
            if should_stop_run(str(error["error_category"])):
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": str(error["error_code"]),
                    "message": str(error["message"]),
                }
                break
""",
    )

    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
