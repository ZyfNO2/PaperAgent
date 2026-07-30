"""Fail a required integration job when its JUnit report contains skips."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def assert_no_skips(path: Path) -> None:
    root = ET.parse(path).getroot()
    skipped = sum(
        int(suite.attrib.get("skipped", "0"))
        for suite in ([root] if root.tag == "testsuite" else root.findall("testsuite"))
    )
    if skipped:
        raise SystemExit(f"required integration suite skipped {skipped} test(s)")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: assert_junit_no_skips.py JUNIT_XML")
    assert_no_skips(Path(args[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
