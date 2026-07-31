from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from evaluation.adapters import AgentAdapter, OfflineFixtureAdapter
from evaluation.judges import judge
from evaluation.judges.llm_judge import run_llm_judge
from evaluation.metrics import collect_case_metrics
from evaluation.report import write_report
from evaluation.schemas import EvaluationCase, EvaluationResult, TerminalState
from paperagent.providers.base import LLMProvider


def load_cases(path: Path) -> tuple[EvaluationCase, ...]:
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = EvaluationCase.model_validate_json(line)
        except Exception as exc:
            raise ValueError(f"invalid evaluation case at {path}:{line_number}: {exc}") from exc
        if case.case_id in seen:
            raise ValueError(f"duplicate case_id at {path}:{line_number}: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError(f"evaluation dataset is empty: {path}")
    return tuple(cases)


async def run_case(
    case: EvaluationCase, adapter: AgentAdapter, *, judge_provider: LLMProvider | None = None
) -> EvaluationResult:
    if case.status != "active":
        return EvaluationResult(
            case=case, status="unverified", error=f"case status is {case.status}"
        )
    if case.mode == "live" and isinstance(adapter, OfflineFixtureAdapter):
        return EvaluationResult(case=case, status="unverified", error="live adapter not configured")
    try:
        trajectory = await asyncio.wait_for(adapter.run(case), timeout=case.timeout_seconds)
        rule = judge(case, trajectory)
        status: Literal["passed", "failed", "waiting_approval", "unverified"]
        if not rule.passed:
            status = "failed"
        elif trajectory.terminal_state == TerminalState.WAITING_APPROVAL:
            status = "waiting_approval"
        else:
            status = "passed"
        llm_result = None
        llm_error = None
        if judge_provider is not None:
            try:
                llm_result = await run_llm_judge(judge_provider, case, trajectory)
            except Exception as exc:
                llm_error = f"{type(exc).__name__}: {exc}"
        return EvaluationResult(
            case=case,
            trajectory=trajectory,
            rule_judge=rule,
            llm_judge=llm_result,
            llm_judge_error=llm_error,
            status=status,
            metrics=collect_case_metrics(trajectory, rule),
        )
    except TimeoutError:
        return EvaluationResult(case=case, status="failed", error="evaluation case timed out")
    except Exception as exc:
        return EvaluationResult(case=case, status="failed", error=f"{type(exc).__name__}: {exc}")


async def run_cases(
    cases: tuple[EvaluationCase, ...],
    adapter: AgentAdapter,
    *,
    max_concurrency: int = 2,
    judge_provider: LLMProvider | None = None,
) -> list[EvaluationResult]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded(case: EvaluationCase) -> EvaluationResult:
        async with semaphore:
            return await run_case(case, adapter, judge_provider=judge_provider)

    return list(await asyncio.gather(*(bounded(case) for case in cases)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PaperAgent agent evaluations")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--category", action="append")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", default=True)
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--enable-llm-judge", action="store_true")
    parser.add_argument("--max-concurrency", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_concurrency < 1:
        raise SystemExit("--max-concurrency must be >= 1")
    judge_provider = None
    if args.enable_llm_judge:
        try:
            from paperagent.providers import build_llm_provider
            from paperagent.providers.config import load_provider_config

            judge_provider = build_llm_provider(load_provider_config())
        except ValueError as exc:
            raise SystemExit(f"LLM judge configuration error: {exc}") from exc
    cases = load_cases(args.dataset)
    if args.case_id:
        cases = tuple(case for case in cases if case.case_id in set(args.case_id))
    if args.category:
        cases = tuple(case for case in cases if case.category in set(args.category))
    if args.live:
        cases = tuple(case for case in cases if case.mode == "live")
    else:
        cases = tuple(case for case in cases if case.mode == "offline")
    if not cases:
        raise SystemExit("no evaluation cases matched the selected filters")
    run_id = "eval_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:6]
    output = args.output or Path("artifacts/evaluations") / run_id
    results = asyncio.run(
        run_cases(
            cases,
            OfflineFixtureAdapter(),
            max_concurrency=args.max_concurrency,
            judge_provider=judge_provider,
        )
    )
    summary = write_report(output, run_id, results)
    print(json.dumps({"output": str(output), **summary["counts"]}, ensure_ascii=False))
    return 1 if summary["counts"].get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
