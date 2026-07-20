from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary
from paperagent.claw_academic_benchmark import evaluate_dataset, load_gold_dataset
from paperagent.claw_benchmark_runtime import (
    build_benchmark_search_runtime,
    execute_benchmark_case,
)
from paperagent.claw_gold_adapter import benchmark_input_from_gold
from paperagent.claw_runtime_evidence import (
    provider_config_for_case,
    summarize_llm_providers,
)
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.providers import FakeSearchProvider
from paperagent.providers.config import load_provider_config
from paperagent.providers.runtime_factory import build_llm_provider
from paperagent.schemas import SearchCandidate


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _load_fake_search(path: Path) -> FakeSearchProvider:
    fixtures: dict[tuple[str, str, int, str], list[SearchCandidate]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw: Any = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError("fixture row must be an object")
            key = (
                str(raw["scenario"]),
                str(raw["query_id"]),
                int(raw["call_index"]),
                str(raw.get("fixture_version", "v0.1")),
            )
            candidates = raw.get("candidates")
            if not isinstance(candidates, list):
                raise ValueError("candidates must be a list")
            fixtures[key] = [SearchCandidate.model_validate(item) for item in candidates]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if not fixtures:
        raise ValueError("fake search fixture file must contain at least one fixture")
    return FakeSearchProvider(fixtures=fixtures)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute PaperAgent on the 20-case CLAW benchmark using either explicit fake "
            "search fixtures or the production Literature Runtime."
        )
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("evals/claw_academic_tailoring_v1"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("build/claw-live-runtime"))
    parser.add_argument("--search-mode", choices=("fake", "literature"), default="fake")
    parser.add_argument("--search-fixtures", type=Path)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-cases", type=int, default=20)
    parser.add_argument("--max-llm-calls", type=int, default=12)
    parser.add_argument(
        "--provider-call-budget",
        type=int,
        default=60,
        help="maximum uncached external search-provider calls across the selected benchmark cases",
    )
    parser.add_argument("--minimum-score", type=int, default=80)
    parser.add_argument("--require-pass", action="store_true")
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument(
        "--llm-price-table",
        type=Path,
        default=(
            Path(os.environ["PAPERAGENT_LLM_PRICE_TABLE"])
            if os.getenv("PAPERAGENT_LLM_PRICE_TABLE")
            else None
        ),
    )
    parser.add_argument(
        "--enable-web-search",
        action="store_true",
        help=(
            "allow Tavily (when keyed) or DuckDuckGo only after a low-risk precise query "
            "fails to produce sufficient verified academic evidence"
        ),
    )
    return parser


def _provider_budget(search_runtime: object) -> dict[str, int | None] | None:
    service = getattr(search_runtime, "service", None)
    reader = getattr(service, "provider_call_budget", None)
    if callable(reader):
        value = reader()
        if isinstance(value, dict):
            return value
    return None


def _workflow_metadata() -> dict[str, object]:
    return {
        "source_sha": os.getenv("PAPERAGENT_SOURCE_SHA") or os.getenv("GITHUB_SHA"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
        "workflow_name": os.getenv("GITHUB_WORKFLOW"),
        "actions_artifact_name": os.getenv("PAPERAGENT_ARTIFACT_NAME"),
    }


def _report_cases(report: object) -> list[dict[str, object]]:
    cases = getattr(report, "cases", ())
    return [
        {
            "case_id": item.case_id,
            "status": item.status,
            "score": item.score,
            "minimum_score": item.minimum_score,
            "expected_decision": item.expected_decision,
            "observed_decision": item.observed_decision,
            "decision_matches": item.decision_matches,
            "hard_failures": [failure.model_dump(mode="json") for failure in item.hard_failures],
        }
        for item in cases
    ]


async def _run(args: argparse.Namespace) -> int:
    dataset = load_gold_dataset(args.dataset_root)
    selected_ids = set(args.case_id)
    cases = [case for case in dataset.cases if not selected_ids or case.case_id in selected_ids]
    if selected_ids - {case.case_id for case in cases}:
        missing = sorted(selected_ids - {case.case_id for case in cases})
        raise ValueError(f"unknown case IDs: {missing}")
    if not 1 <= args.max_cases <= 20:
        raise ValueError("--max-cases must be between 1 and 20")
    if args.max_llm_calls < 1:
        raise ValueError("--max-llm-calls must be positive")
    if args.provider_call_budget < 1:
        raise ValueError("--provider-call-budget must be positive")
    cases = cases[: args.max_cases]

    leakage_audit = audit_benchmark_execution_boundary()
    if not leakage_audit.passed:
        raise RuntimeError(f"static benchmark leakage audit failed: {leakage_audit.findings}")

    fake_provider = None
    if args.search_mode == "fake":
        if args.search_fixtures is None:
            raise ValueError("--search-fixtures is required in fake mode")
        fake_provider = _load_fake_search(args.search_fixtures)

    literature_settings = LiteratureProviderSettings(
        contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
        enable_web_search=bool(args.enable_web_search),
        max_provider_calls_total=args.provider_call_budget,
    )
    search_runtime = build_benchmark_search_runtime(
        args.search_mode,
        settings=literature_settings,
        fake_provider=fake_provider,
    )
    provider_config = load_provider_config(
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
    )
    price_table = load_price_table(args.llm_price_table) if args.llm_price_table else None
    case_provider_config = provider_config_for_case(
        provider_config,
        selected_case_count=len(cases),
    )

    states: list[object] = []
    traces = []
    providers: list[object] = []
    errors: list[dict[str, str]] = []
    runtime_failures: list[str] = []
    provider_budget: dict[str, int | None] | None = None
    try:
        for index, case in enumerate(cases, start=1):
            llm = build_llm_provider(case_provider_config, price_table)
            providers.append(llm)
            try:
                state, trace = await execute_benchmark_case(
                    benchmark_input=benchmark_input_from_gold(case),
                    case_id=case.case_id,
                    llm=llm,
                    search=search_runtime.adapter,
                    max_llm_calls=args.max_llm_calls,
                    task_id=f"claw-{index:02d}-{case.case_id}",
                )
            except Exception as exc:
                errors.append(
                    {
                        "case_id": case.case_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                continue
            states.append({"case_id": case.case_id, "state": state})
            traces.append(trace)
        provider_budget = _provider_budget(search_runtime)
    finally:
        await search_runtime.aclose()

    llm_summary = summarize_llm_providers(
        providers,
        config=provider_config,
        price_table=price_table,
        selected_case_count=len(cases),
    )
    if provider_config.max_estimated_cost_usd is not None:
        if llm_summary["cost_estimate_complete"] is not True:
            runtime_failures.append("LLM cost estimate is incomplete under a configured hard cap")
        elif llm_summary["within_configured_cost"] is not True:
            runtime_failures.append("estimated LLM cost exceeded the configured full-run hard cap")

    output_dir: Path = args.output_dir
    _write_jsonl(output_dir / "states.jsonl", states)
    _write_jsonl(
        output_dir / "run-traces.jsonl",
        [trace.model_dump(mode="json", by_alias=True) for trace in traces],
    )
    summary: dict[str, object] = {
        "schema": "paperagent.claw-paid-full-runtime-summary.v1",
        **_workflow_metadata(),
        "search_mode": args.search_mode,
        "web_search_enabled": bool(args.enable_web_search),
        "static_leakage_audit": {
            "passed": leakage_audit.passed,
            "findings": list(leakage_audit.findings),
        },
        "selected_cases": [case.case_id for case in cases],
        "selected_case_count": len(cases),
        "completed": len(traces),
        "completed_case_ids": [trace.case_id for trace in traces],
        "errors": errors,
        "runtime_failures": runtime_failures,
        "provider_call_budget": provider_budget,
        "llm": llm_summary,
        "report_status": "not_generated",
        "output_files": {
            "states": "states.jsonl",
            "run_traces": "run-traces.jsonl",
            "report": None,
            "execution_summary": "execution-summary.json",
        },
        "passed": False,
    }
    exit_code = 1 if errors or runtime_failures else 0
    if len(cases) == 20 and len(traces) == 20:
        report = evaluate_dataset(dataset, tuple(traces), minimum_score=args.minimum_score)
        _write_json(output_dir / "report.json", report.model_dump(mode="json", by_alias=True))
        report_passed = (
            report.failed == 0
            and report.hard_failure_count == 0
            and not errors
            and not runtime_failures
        )
        summary.update(
            {
                "report_status": "generated",
                "passed": report_passed,
                "passed_cases": report.passed,
                "failed": report.failed,
                "hard_failure_count": report.hard_failure_count,
                "average_score": report.average_score,
                "decision_accuracy": report.decision_accuracy,
                "report_digest": report.report_digest,
                "cases": _report_cases(report),
                "output_files": {
                    **summary["output_files"],
                    "report": "report.json",
                },
            }
        )
        if args.require_pass and not report_passed:
            exit_code = 1
    elif args.require_pass:
        runtime_failures.append("formal report requires exactly 20 completed cases")
        summary["runtime_failures"] = runtime_failures
        exit_code = 1
    _write_json(output_dir / "execution-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


def main() -> int:
    args = _parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
