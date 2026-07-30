"""Fail CI when raw coverage is below the configured threshold."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def assert_coverage(path: Path, threshold: float) -> float:
    payload = json.loads(path.read_text(encoding="utf-8"))
    actual = float(payload["totals"]["percent_covered"])
    if actual < threshold:
        raise SystemExit(f"raw coverage {actual:.12f}% is below required {threshold:.12f}%")
    print(f"raw coverage {actual:.12f}% >= {threshold:.12f}%")
    return actual


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        raise SystemExit("usage: assert_coverage_threshold.py COVERAGE_JSON THRESHOLD")
    assert_coverage(Path(args[0]), float(args[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
