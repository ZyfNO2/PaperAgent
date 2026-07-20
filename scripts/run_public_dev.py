from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.score_runs import load_jsonl, project_runtime_input, score_dataset
except ModuleNotFoundError:  # Direct script execution sets scripts/ as sys.path[0].
    from score_runs import load_jsonl, project_runtime_input, score_dataset


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, values: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _report_digest(report: dict[str, Any]) -> str:
    value = {key: item for key, item in report.items() if key != "report_digest"}
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _metamorphic_consistency(
    cases: list[dict[str, Any]], traces: list[dict[str, Any]]
) -> tuple[float | None, int]:
    decisions = {trace["case_id"]: trace.get("decision") for trace in traces}
    groups: dict[str, list[object]] = {}
    for case in cases:
        group = case["metadata"].get("metamorphic_group")
        if not isinstance(group, str) or not group:
            continue
        groups.setdefault(group, []).append(decisions.get(case["case_id"]))
    comparable = [values for values in groups.values() if len(values) >= 2]
    if not comparable:
        return None, 0
    consistent = sum(len(set(values)) == 1 for values in comparable)
    return consistent / len(comparable), len(comparable)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the visible Academic Method Holdout v2 development cases through an "
            "installed PaperAgent production commit. Oracle and metadata remain external."
        )
    )
    parser.add_argument("--cases", type=Path, default=Path("data/public-dev-v2.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/public-dev-v2"))
    parser.add_argument("--max-cases", type=int, default=12)
    parser.add_argument("--max-llm-calls", type=int, default=12)
    parser.add_argument("--provider-call-budget", type=int, default=120)
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
    if not 1 <= args.max_cases <= len(cases):
        raise ValueError(f"--max-cases must be between 1 and {len(cases)}")
    selected = cases[: args.max_cases]
    budgets = allocate_case_budgets(args.provider_call_budget, len(selected))

    leakage = audit_benchmark_execution_boundary()
    if not leakage.passed:
        raise RuntimeError(f"production leakage audit failed: {leakage.findings}")

    provider_config = load_provider_config(
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
    )
    price_table = load_price_table(args.llm_price_table) if args.llm_price_table else None

    projected_inputs: list[object] = []
    states: list[object] = []
    traces: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for index, (case, provider_budget) in enumerate(zip(selected, budgets, strict=True), start=1):
        projected = project_runtime_input(case)
        benchmark_input = BenchmarkInput.model_validate(projected)
        projected_inputs.append(
            {
                "external_case_id": case["case_id"],
                "runtime_input": benchmark_input.model_dump(mode="json"),
            }
        )
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
            primitive, state = await execute_benchmark_input(
                benchmark_input=benchmark_input,
                llm=llm,
                search=search_runtime.adapter,
                max_llm_calls=args.max_llm_calls,
                task_id=f"public-dev-runtime-{index:03d}",
            )
            trace = normalize_paperagent_state(
                state,
                BenchmarkNormalizationContext(
                    case_id=case["case_id"],
                    future_or_test_leakage=not leakage.passed,
                    leakage_findings=leakage.findings,
                ),
            )
            states.append({"case_id": case["case_id"], "state": primitive})
            traces.append(trace.model_dump(mode="json", by_alias=True))
        except Exception as exc:
            errors.append(
                {
                    "case_id": case["case_id"],
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
        finally:
            await search_runtime.aclose()

    output_dir: Path = args.output_dir
    _write_jsonl(output_dir / "runtime-inputs.jsonl", projected_inputs)
    _write_jsonl(output_dir / "states.jsonl", states)
    _write_jsonl(output_dir / "run-traces.jsonl", traces)

    report = score_dataset(selected, traces) if not errors and len(traces) == len(selected) else None
    metamorphic_consistency: float | None = None
    metamorphic_group_count = 0
    if report is not None:
        metamorphic_consistency, metamorphic_group_count = _metamorphic_consistency(selected, traces)
        report["metamorphic_decision_consistency"] = metamorphic_consistency
        report["metamorphic_group_count"] = metamorphic_group_count
        report["report_digest"] = _report_digest(report)
        _write_json(output_dir / "report.json", report)

    metamorphic_passed = metamorphic_consistency is None or metamorphic_consistency >= 0.85
    thresholds_passed = bool(
        report is not None
        and report["decision_accuracy"] >= 0.80
        and report["hard_failure_count"] == 0
        and report["fabricated_evidence_count"] == 0
        and report["unsupported_comparator_count"] == 0
        and metamorphic_passed
    )
    summary = {
        "schema": "paperagent.academic-holdout.public-dev-run.v2",
        "split": "development",
        "result_interpretation": "public development set; not independent generalization evidence",
        "production_source_sha": os.getenv("PAPERAGENT_PRODUCTION_SHA"),
        "benchmark_source_sha": os.getenv("GITHUB_SHA"),
        "selected_case_count": len(selected),
        "completed_case_count": len(traces),
        "errors": errors,
        "static_leakage_audit": {
            "passed": leakage.passed,
            "findings": list(leakage.findings),
        },
        "thresholds": {
            "decision_accuracy_minimum": 0.80,
            "hard_failures_maximum": 0,
            "fabricated_evidence_maximum": 0,
            "unsupported_comparator_maximum": 0,
            "metamorphic_decision_consistency_minimum": 0.85,
            "public_private_score_gap_maximum_percentage_points": 10,
        },
        "thresholds_passed": thresholds_passed,
        "report": report,
    }
    _write_json(output_dir / "execution-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    if errors:
        return 1
    if args.require_thresholds and not thresholds_passed:
        return 1
    return 0


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
