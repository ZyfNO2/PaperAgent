from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from paperagent.claw_academic_benchmark import evaluate_dataset, load_gold_dataset
from paperagent.claw_benchmark_runtime import (
    build_benchmark_search_runtime,
    execute_benchmark_case,
)
from paperagent.literature.factory import LiteratureProviderSettings
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
    parser.add_argument("--minimum-score", type=int, default=80)
    parser.add_argument("--require-pass", action="store_true")
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument(
        "--enable-web-search",
        action="store_true",
        help="enable Tavily (when keyed) and DuckDuckGo only as post-academic fallback",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    dataset = load_gold_dataset(args.dataset_root)
    selected_ids = set(args.case_id)
    cases = [case for case in dataset.cases if not selected_ids or case.case_id in selected_ids]
    if selected_ids - {case.case_id for case in cases}:
        missing = sorted(selected_ids - {case.case_id for case in cases})
        raise ValueError(f"unknown case IDs: {missing}")
    if not 1 <= args.max_cases <= 20:
        raise ValueError("--max-cases must be between 1 and 20")
    cases = cases[: args.max_cases]

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
    llm = build_llm_provider(provider_config, None)

    states: list[object] = []
    traces = []
    errors: list[dict[str, str]] = []
    try:
        for index, case in enumerate(cases, start=1):
            try:
                state, trace = await execute_benchmark_case(
                    case=case,
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
    finally:
        await search_runtime.aclose()

    output_dir: Path = args.output_dir
    _write_jsonl(output_dir / "states.jsonl", states)
    _write_jsonl(
        output_dir / "run-traces.jsonl",
        [trace.model_dump(mode="json", by_alias=True) for trace in traces],
    )
    summary: dict[str, object] = {
        "search_mode": args.search_mode,
        "web_search_enabled": bool(args.enable_web_search),
        "selected_cases": [case.case_id for case in cases],
        "completed": len(traces),
        "errors": errors,
        "report_status": "not_generated",
    }
    exit_code = 1 if errors else 0
    if len(cases) == 20 and len(traces) == 20:
        report = evaluate_dataset(dataset, tuple(traces), minimum_score=args.minimum_score)
        _write_json(output_dir / "report.json", report.model_dump(mode="json", by_alias=True))
        summary.update(
            {
                "report_status": "generated",
                "passed": report.passed,
                "failed": report.failed,
                "average_score": report.average_score,
                "decision_accuracy": report.decision_accuracy,
                "report_digest": report.report_digest,
            }
        )
        if args.require_pass and report.failed:
            exit_code = 1
    _write_json(output_dir / "execution-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


def main() -> int:
    args = _parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
