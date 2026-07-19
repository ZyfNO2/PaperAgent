from __future__ import annotations

import argparse
from pathlib import Path

from paperagent.gold_case import GoldCaseReport
from paperagent.interview_readiness import render_interview_readiness


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build interview evidence from a Gold Case report.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = GoldCaseReport.model_validate_json(args.input.read_text(encoding="utf-8"))
    rendered = render_interview_readiness(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Interview readiness written to {args.output}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
