"""Fail CI when raw coverage is below the configured threshold."""

from __future__ import annotations

import sys
from pathlib import Path

from paperagent.ci_evidence import assert_coverage


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        raise SystemExit("usage: assert_coverage_threshold.py COVERAGE_JSON THRESHOLD")
    assert_coverage(Path(args[0]), float(args[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
