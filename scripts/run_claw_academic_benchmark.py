from __future__ import annotations

import argparse
import json
from pathlib import Path

from paperagent.claw_academic_benchmark import (
    AcademicTailoringRunTrace,
    evaluate_dataset,
    load_gold_dataset,
    run_gold_self_check,
)


def _load_run_traces(path: Path) -> tuple[AcademicTailoringRunTrace, ...]:
    traces: list[AcademicTailoringRunTrace] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            traces.append(AcademicTailoringRunTrace.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if not traces:
        raise ValueError("candidate run JSONL must contain at least one trace")
    return tuple(traces)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or score PaperAgent traces against the read-only PaperClaw "
            "Academic Tailoring Gold Benchmark v1 snapshot."
        )
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("evals/claw_academic_tailoring_v1"),
    )
    parser.add_argument(
        "--runs",
        type=Path,
        help="JSONL file containing normalized PaperAgent run traces",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/claw-academic-tailoring-report.json"),
    )
    parser.add_argument("--minimum-score", type=int, default=80)
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="exit non-zero when any case fails",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 0 <= args.minimum_score <= 100:
        raise ValueError("minimum score must be between 0 and 100")
    if args.runs is None:
        report = run_gold_self_check(
            args.dataset_root,
            minimum_score=args.minimum_score,
        )
        mode = "evaluator-self-check"
    else:
        dataset = load_gold_dataset(args.dataset_root)
        report = evaluate_dataset(
            dataset,
            _load_run_traces(args.runs),
            minimum_score=args.minimum_score,
        )
        mode = "candidate-run"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "mode": mode,
                "source_commit": report.source_commit,
                "dataset_digest": report.dataset_digest,
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "average_score": report.average_score,
                "decision_accuracy": report.decision_accuracy,
                "hard_failure_count": report.hard_failure_count,
                "report_digest": report.report_digest,
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.require_pass and report.failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
