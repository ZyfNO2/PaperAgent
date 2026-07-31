"""Fail a required integration job when its JUnit report contains skips."""

from __future__ import annotations

import sys
from pathlib import Path

from paperagent.ci_evidence import assert_no_skips


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: assert_junit_no_skips.py JUNIT_XML")
    assert_no_skips(Path(args[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
