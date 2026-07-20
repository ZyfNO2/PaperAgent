from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.run_public_dev import _metamorphic_consistency
    from scripts.score_runs import load_jsonl, project_runtime_input, score_dataset
except ModuleNotFoundError:  # Direct script execution sets scripts/ as sys.path[0].
    from run_public_dev import _metamorphic_consistency
    from score_runs import load_jsonl, project_runtime_input, score_dataset


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _canonical_digest(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a sealed Academic Method Holdout v2 dataset and emit aggregate metrics only. "
            "The runner never writes prompts, states, raw traces, or per-case scores."
        )
    )
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--public-report", type=Path, required=True)
    parser.add_argument("--production-scan", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, default=32)
    parser.add_argument("--max-llm-calls", type=int, default=12)
    parser.add_argument("--provider-call-budget", type=int, default=320)
    parser.add_argument("--llm-provider", default="mistral")
    parser.add_argument("--llm-model", default="mistral-small-latest")
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-price-table", type=Path)
    parser.add_argument("--require-thresholds", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> int:
    from paperagent.benchmark_input import BenchmarkInput
    from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary
    from paperagent.claw_benchmark_normalizer import (
        BenchmarkNormalizationContext,
        normalize_paperagent_state,
    )
    from paperagent.claw_benchmark_runtime import (
        build_benchmark_search_runtime,
        execute_benchmark_input,
    )
    from paperagent.claw_runtime_evidence import allocate_case_budgets
    from paperagent.literature.factory import LiteratureProviderSettings
    from paperagent.pricing import load_price_table
    from paperagent.providers.config import load_provider_config
    from paperagent.providers.runtime_factory import build_llm_provider

    cases = load_jsonl(args.cases)
    if len(cases) != args.expected_cases:
        raise ValueError(f"expected {args.expected_cases} sealed cases, found {len(cases)}")

    public_handoff: Any = json.loads(args.public_report.read_text(encoding="utf-8"))
    public_summary = public_handoff.get("summary") if isinstance(public_handoff, dict) else None
    public_report = public_summary.get("report") if isinstance(public_summary, dict) else None
    if not isinstance(public_report, dict):
        raise ValueError("public report does not contain a completed structured report")

    production_scan: Any = json.loads(args.production_scan.read_text(encoding="utf-8"))
    if not isinstance(production_scan, dict) or production_scan.get("passed") is not True:
        raise ValueError("private production scan must pass before execution")

    freeze: Any = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    if not isinstance(freeze, dict):
        raise ValueError("freeze manifest must be an object")
    thresholds = freeze.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("freeze manifest lacks thresholds")

    leakage = audit_benchmark_execution_boundary()
    if not leakage.passed:
        raise RuntimeError(f"production leakage audit failed: {leakage.findings}")

    provider_config = load_provider_config(
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
    )
    price_table = load_price_table(args.llm_price_table) if args.llm_price_table else None
    budgets = allocate_case_budgets(args.provider_call_budget, len(cases))

    traces: list[dict[str, Any]] = []
    runtime_error_types: list[str] = []
    for index, (case, provider_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
        benchmark_input = BenchmarkInput.model_validate(project_runtime_input(case))
        search_runtime = build_benchmark_search_runtime(
            "literature",
            settings=LiteratureProviderSettings(
                contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
                semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
                tavily_api_key=None,
                enable_web_search=False,
                max_provider_calls_total=provider_budget,
            ),
        )
        llm = build_llm_provider(provider_config, price_table)
        try:
            _, state = await execute_benchmark_input(
                benchmark_input=benchmark_input,
                llm=llm,
                search=search_runtime.adapter,
                max_llm_calls=args.max_llm_calls,
                task_id=f"private-holdout-runtime-{index:03d}",
            )
            trace = normalize_paperagent_state(
                state,
                BenchmarkNormalizationContext(
                    case_id=case["case_id"],
                    future_or_test_leakage=not leakage.passed,
                    leakage_findings=leakage.findings,
                ),
            )
            traces.append(trace.model_dump(mode="json", by_alias=True))
            print(f"sealed case {index}/{len(cases)} completed")
        except Exception as exc:
            runtime_error_types.append(type(exc).__name__)
            print(f"sealed case {index}/{len(cases)} failed: {type(exc).__name__}")
        finally:
            await search_runtime.aclose()

    structured = score_dataset(cases, traces) if not runtime_error_types and len(traces) == len(cases) else None
    metamorphic_consistency: float | None = None
    metamorphic_group_count = 0
    if structured is not None:
        metamorphic_consistency, metamorphic_group_count = _metamorphic_consistency(cases, traces)

    public_average = float(public_report["average_score"])
    private_average = float(structured["average_score"]) if structured is not None else 0.0
    score_gap = abs(public_average - private_average)
    adapter_created_pilot_count = 0 if production_scan.get("passed") is True else 1

    metrics = {
        "completed_case_count": len(traces),
        "runtime_error_count": len(runtime_error_types),
        "runtime_error_types": sorted(runtime_error_types),
        "decision_accuracy": structured["decision_accuracy"] if structured is not None else 0.0,
        "average_score": private_average,
        "hard_failure_count": structured["hard_failure_count"] if structured is not None else -1,
        "fabricated_evidence_count": (
            structured["fabricated_evidence_count"] if structured is not None else -1
        ),
        "unsupported_comparator_count": (
            structured["unsupported_comparator_count"] if structured is not None else -1
        ),
        "adapter_created_pilot_count": adapter_created_pilot_count,
        "metamorphic_decision_consistency": metamorphic_consistency,
        "metamorphic_group_count": metamorphic_group_count,
        "public_average_score": public_average,
        "public_private_score_gap_percentage_points": score_gap,
    }

    metamorphic_passed = (
        metamorphic_consistency is not None
        and metamorphic_consistency
        >= float(thresholds["metamorphic_decision_consistency_minimum"])
    )
    thresholds_passed = bool(
        structured is not None
        and len(traces) == args.expected_cases
        and metrics["decision_accuracy"] >= float(thresholds["decision_accuracy_minimum"])
        and metrics["hard_failure_count"] <= int(thresholds["hard_failure_count_maximum"])
        and metrics["fabricated_evidence_count"]
        <= int(thresholds["fabricated_evidence_count_maximum"])
        and metrics["unsupported_comparator_count"]
        <= int(thresholds["unsupported_comparator_count_maximum"])
        and metrics["adapter_created_pilot_count"]
        <= int(thresholds["adapter_created_pilot_count_maximum"])
        and metamorphic_passed
        and score_gap
        <= float(thresholds["public_private_score_gap_maximum_percentage_points"])
    )

    aggregate = {
        "schema": "paperagent.academic-holdout.private-aggregate.v2",
        "split": "private_holdout",
        "result_language": "The frozen system was evaluated once on a previously unseen private holdout.",
        "production_source_sha": os.getenv("PAPERAGENT_PRODUCTION_SHA"),
        "benchmark_source_sha": os.getenv("PAPERAGENT_BENCHMARK_SHA"),
        "freeze_digest": freeze.get("freeze_digest"),
        "private_cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        "production_scan_digest": production_scan.get("production_digest"),
        "thresholds": thresholds,
        "metrics": metrics,
        "thresholds_passed": thresholds_passed,
    }
    aggregate["aggregate_digest"] = _canonical_digest(aggregate)
    _write_json(args.output, aggregate)
    print(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True))

    if args.require_thresholds and not thresholds_passed:
        return 1
    return 0 if not runtime_error_types else 1


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
