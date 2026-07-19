from __future__ import annotations

import argparse
from pathlib import Path

from paperagent.gold_case import run_gold_case


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic PaperAgent academic-tailoring Gold Case."
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_gold_case(args.repository_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        "Gold Case",
        report.status.upper(),
        f"decision={report.proposal_decision}",
        f"score={report.grade_score}/{report.minimum_score}",
        f"digest={report.report_digest}",
    )
    print("Scientific acceptance: NOT CLAIMED")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
