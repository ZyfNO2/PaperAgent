from __future__ import annotations

import argparse
import json
from pathlib import Path

from paperagent.evaluation import EvaluationObservation, build_report, load_cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic PaperAgent evaluation report"
    )
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.cases)
    observations = tuple(
        EvaluationObservation.model_validate_json(line)
        for line in args.observations.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    report = build_report(cases, observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
