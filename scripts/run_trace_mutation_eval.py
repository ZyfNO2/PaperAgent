from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from paperagent.schemas.trace import TraceEvent
from paperagent.trace_replay import (
    TraceFixtureManifest,
    TraceMutationCase,
    apply_trace_mutation,
    build_trace_replay_report,
)

_TRACE_LIST = TypeAdapter(list[TraceEvent])
_CASE_LIST = TypeAdapter(list[TraceMutationCase])


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay the deterministic trace fixture and verify the mutation corpus."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("evals/cloud_trace/steel-defect-pollution-001"),
    )
    parser.add_argument(
        "--source-commit",
        default=os.getenv("GITHUB_SHA", "local-uncommitted"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/trace-mutation-eval/report.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    fixture_dir: Path = args.fixture_dir
    manifest = TraceFixtureManifest.model_validate(_load_json(fixture_dir / "manifest.json"))
    baseline = _TRACE_LIST.validate_python(_load_json(fixture_dir / "trace.json"))
    cases = _CASE_LIST.validate_python(_load_json(fixture_dir / "cases.json"))

    case_results: list[dict[str, Any]] = []
    corpus_passed = True
    for case in cases:
        events = apply_trace_mutation(baseline, case.mutation)
        report = build_trace_replay_report(
            case_id=case.case_id,
            fixture_version=manifest.fixture_version,
            source_commit=args.source_commit,
            events=events,
            expected_event_count=case.expected_event_count or manifest.expected_event_count,
            expected_route_sequence=(
                case.expected_route_sequence
                if case.expected_route_sequence is not None
                else manifest.expected_route_sequence
            ),
            expected_trace_digest=(
                case.expected_trace_digest or manifest.expected_trace_digest
            ),
        )
        required_errors_present = set(case.required_error_codes).issubset(report.error_codes)
        classified_correctly = report.passed == case.expected_pass and required_errors_present
        corpus_passed = corpus_passed and classified_correctly
        case_results.append(
            {
                "case_id": case.case_id,
                "mutation": case.mutation,
                "expected_pass": case.expected_pass,
                "actual_pass": report.passed,
                "required_error_codes": case.required_error_codes,
                "actual_error_codes": report.error_codes,
                "classified_correctly": classified_correctly,
                "replay_report": report.model_dump(mode="json"),
            }
        )

    payload = {
        "schema_version": "0.1",
        "fixture_case_id": manifest.case_id,
        "fixture_version": manifest.fixture_version,
        "source_commit": args.source_commit,
        "total_cases": len(cases),
        "negative_cases": sum(1 for case in cases if not case.expected_pass),
        "passed_cases": sum(1 for result in case_results if result["classified_correctly"]),
        "failed_cases": sum(1 for result in case_results if not result["classified_correctly"]),
        "corpus_passed": corpus_passed,
        "cases": case_results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if corpus_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
