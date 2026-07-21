from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paperagent.benchmark_input import BenchmarkInput
from paperagent.claw_benchmark_runtime import build_benchmark_search_runtime, execute_benchmark_case
from paperagent.claw_runtime_evidence import allocate_case_budgets, provider_config_for_case
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.providers.config import load_provider_config
from paperagent.providers.runtime_factory import build_llm_provider

from run_academic_tailoring_retrieval_v1 import (
    AuditedLLMProvider,
    _FATAL_PROVIDER_ERROR_CODES,
    _assert_gold_absent,
    _build_runtime_summary,
    _fatal_provider_error_code_from_trace,
    _load_public_dataset,
    _normalize_provider_error_code,
    _write_runtime_outputs,
)


@dataclass(slots=True)
class CaseResult:
    index: int
    case_id: str
    elapsed_seconds: float
    state: dict[str, Any] | None = None
    trace: dict[str, object] | None = None
    error: dict[str, str] | None = None
    fatal_provider_error: dict[str, str] | None = None
    completed: bool = False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Gold-free academic tailoring retrieval set with case concurrency"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--max-llm-calls", type=int, default=10)
    parser.add_argument("--provider-call-budget", type=int, default=80)
    parser.add_argument(
        "--case-concurrency",
        type=int,
        default=int(os.getenv("PAPERAGENT_CASE_CONCURRENCY", "1")),
    )
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-price-table", type=Path, default=None)
    parser.add_argument("--enable-web-search", action="store_true")
    parser.add_argument("--allow-gold-in-workspace", action="store_true")
    return parser


async def _execute_case(
    *,
    index: int,
    case: dict[str, object],
    search_budget: int,
    case_provider_config: object,
    price_table: object,
    prompt_log: Path,
    max_llm_calls: int,
    enable_web_search: bool,
) -> CaseResult:
    case_id = str(case["case_id"])
    started = time.monotonic()
    search_runtime = None
    try:
        search_runtime = build_benchmark_search_runtime(
            "literature",
            settings=LiteratureProviderSettings(
                contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
                semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
                tavily_api_key=os.getenv("TAVILY_API_KEY"),
                enable_web_search=enable_web_search,
                max_provider_calls_total=search_budget,
            ),
        )
        llm = AuditedLLMProvider(
            build_llm_provider(case_provider_config, price_table),
            prompt_log=prompt_log,
            case_id=case_id,
        )
        benchmark_input = BenchmarkInput.model_validate(case["benchmark_input"])
        state, trace = await execute_benchmark_case(
            benchmark_input=benchmark_input,
            case_id=case_id,
            llm=llm,
            search=search_runtime.adapter,
            max_llm_calls=max_llm_calls,
            task_id=f"atr-v1-{index:02d}",
        )
        trace_payload = trace.model_dump(mode="json", by_alias=True)
        fatal_code = _fatal_provider_error_code_from_trace(trace_payload)
        if fatal_code is not None:
            return CaseResult(
                index=index,
                case_id=case_id,
                elapsed_seconds=time.monotonic() - started,
                state=state,
                trace=trace_payload,
                error={
                    "case_id": case_id,
                    "error_type": "FatalLLMProviderError",
                    "message": fatal_code,
                },
                fatal_provider_error={
                    "case_id": case_id,
                    "code": fatal_code,
                    "message": "fatal LLM provider failure surfaced in the case trace",
                },
            )
        execution = state.get("execution")
        execution_status = execution.get("status") if isinstance(execution, dict) else None
        if execution_status != "completed":
            return CaseResult(
                index=index,
                case_id=case_id,
                elapsed_seconds=time.monotonic() - started,
                state=state,
                trace=trace_payload,
                error={
                    "case_id": case_id,
                    "error_type": "CaseExecutionIncomplete",
                    "message": f"execution status was {execution_status!r}",
                },
            )
        return CaseResult(
            index=index,
            case_id=case_id,
            elapsed_seconds=time.monotonic() - started,
            state=state,
            trace=trace_payload,
            completed=True,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        normalized = _normalize_provider_error_code(getattr(exc, "error_code", None))
        normalized = normalized or _normalize_provider_error_code(getattr(exc, "code", None))
        fatal = normalized if normalized in _FATAL_PROVIDER_ERROR_CODES else None
        return CaseResult(
            index=index,
            case_id=case_id,
            elapsed_seconds=time.monotonic() - started,
            error={
                "case_id": case_id,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            fatal_provider_error=(
                {
                    "case_id": case_id,
                    "code": fatal,
                    "message": "fatal LLM provider failure raised before case completion",
                }
                if fatal is not None
                else None
            ),
        )
    finally:
        if search_runtime is not None:
            await search_runtime.aclose()


async def _run(args: argparse.Namespace) -> int:
    if not args.allow_gold_in_workspace:
        _assert_gold_absent(Path.cwd())
    dataset = _load_public_dataset(args.dataset)
    cases = list(dataset["cases"])
    selected = set(args.case_id)
    if selected:
        cases = [case for case in cases if case.get("case_id") in selected]
        missing = selected - {str(case.get("case_id")) for case in cases}
        if missing:
            raise ValueError(f"unknown case IDs: {sorted(missing)}")
    if not 1 <= args.max_cases <= 10:
        raise ValueError("--max-cases must be between 1 and 10")
    if not 1 <= args.case_concurrency <= 10:
        raise ValueError("--case-concurrency must be between 1 and 10")
    if args.max_llm_calls < 1 or args.provider_call_budget < 1:
        raise ValueError("LLM and provider budgets must be positive")
    cases = cases[: args.max_cases]

    from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary

    leakage_audit = audit_benchmark_execution_boundary()
    if not leakage_audit.passed:
        raise RuntimeError(f"static leakage audit failed: {leakage_audit.findings}")

    output_dir: Path = args.output_dir
    prompt_log = output_dir / "prompt-log.jsonl"
    prompt_log.parent.mkdir(parents=True, exist_ok=True)
    prompt_log.write_text("", encoding="utf-8")

    provider_config = load_provider_config(
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
    )
    price_table_path = args.llm_price_table
    if price_table_path is None and os.getenv("PAPERAGENT_LLM_PRICE_TABLE"):
        price_table_path = Path(os.environ["PAPERAGENT_LLM_PRICE_TABLE"])
    price_table = load_price_table(price_table_path) if price_table_path else None
    budgets = allocate_case_budgets(args.provider_call_budget, len(cases))
    case_provider_config = provider_config_for_case(
        provider_config,
        selected_case_count=len(cases),
        max_logical_calls=args.max_llm_calls,
    )

    states: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    attempted_case_ids: list[str] = []
    completed_case_count = 0
    fatal_provider_error: dict[str, str] | None = None
    run_started = time.monotonic()

    def persist_checkpoint() -> dict[str, object]:
        summary = _build_runtime_summary(
            cases=cases,
            dataset=dataset,
            attempted_case_ids=attempted_case_ids,
            completed_case_count=completed_case_count,
            traces=traces,
            errors=errors,
            fatal_provider_error=fatal_provider_error,
            prompt_records=sum(
                1 for line in prompt_log.read_text(encoding="utf-8").splitlines() if line
            ),
            leakage_passed=leakage_audit.passed,
            leakage_findings=list(leakage_audit.findings),
            allow_gold_in_workspace=args.allow_gold_in_workspace,
        )
        summary["case_concurrency"] = args.case_concurrency
        summary["hedging"] = {
            "max_requests": int(os.getenv("PAPERAGENT_LLM_MAX_HEDGED_REQUESTS", "1")),
            "delay_seconds": float(os.getenv("PAPERAGENT_LLM_HEDGE_DELAY_SECONDS", "0")),
            "cancellation": "best_effort",
        }
        summary["elapsed_seconds"] = round(time.monotonic() - run_started, 3)
        _write_runtime_outputs(
            output_dir=output_dir,
            states=states,
            traces=traces,
            summary=summary,
        )
        return summary

    pending: dict[asyncio.Task[CaseResult], tuple[int, str]] = {}
    next_case = 0

    def schedule_one() -> None:
        nonlocal next_case
        index = next_case + 1
        case = cases[next_case]
        search_budget = budgets[next_case]
        case_id = str(case["case_id"])
        attempted_case_ids.append(case_id)
        task = asyncio.create_task(
            _execute_case(
                index=index,
                case=case,
                search_budget=search_budget,
                case_provider_config=case_provider_config,
                price_table=price_table,
                prompt_log=prompt_log,
                max_llm_calls=args.max_llm_calls,
                enable_web_search=bool(args.enable_web_search),
            )
        )
        pending[task] = (index, case_id)
        next_case += 1
        persist_checkpoint()
        print(
            json.dumps(
                {
                    "event": "case_started",
                    "case_id": case_id,
                    "index": index,
                    "active_cases": len(pending),
                    "attempted": len(attempted_case_ids),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )

    while next_case < len(cases) and len(pending) < args.case_concurrency:
        schedule_one()

    while pending:
        done, _ = await asyncio.wait(tuple(pending), return_when=asyncio.FIRST_COMPLETED)
        fatal_seen = False
        for task in done:
            pending.pop(task)
            result = task.result()
            if result.state is not None:
                states.append({"case_id": result.case_id, "state": result.state})
            if result.trace is not None:
                traces.append(result.trace)
            if result.error is not None:
                errors.append(result.error)
            if result.completed:
                completed_case_count += 1
            if result.fatal_provider_error is not None:
                fatal_provider_error = result.fatal_provider_error
                fatal_seen = True

            checkpoint = persist_checkpoint()
            print(
                json.dumps(
                    {
                        "event": "case_finished",
                        "case_id": result.case_id,
                        "index": result.index,
                        "elapsed_seconds": round(result.elapsed_seconds, 3),
                        "completed": result.completed,
                        "attempted": len(attempted_case_ids),
                        "completed_total": completed_case_count,
                        "errors": len(errors),
                        "fatal_provider_error": fatal_provider_error,
                        "active_cases": len(pending),
                        "passed_so_far": checkpoint["passed"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )

        if fatal_seen:
            for task, (_, case_id) in tuple(pending.items()):
                errors.append(
                    {
                        "case_id": case_id,
                        "error_type": "CancelledAfterFatalProviderError",
                        "message": "cancelled after another concurrent case hit a fatal provider error",
                    }
                )
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            pending.clear()
            persist_checkpoint()
            break

        while next_case < len(cases) and len(pending) < args.case_concurrency:
            schedule_one()

    summary = persist_checkpoint()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
