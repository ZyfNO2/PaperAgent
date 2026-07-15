#!/usr/bin/env python3
"""Fail CI only when a head pytest run introduces failures beyond baseline.

The repository's full API suite currently contains historical failures outside
Re8.2. Running the suite remains useful, but treating every pre-existing failure
as a regression makes the check permanently red. This comparator keeps both
JUnit reports, prints the baseline debt, and blocks only head-only failures or
errors.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class FailedCase:
    classname: str
    name: str
    kind: str

    @property
    def id(self) -> str:
        prefix = f"{self.classname}::" if self.classname else ""
        return f"{prefix}{self.name} [{self.kind}]"


def _failed_cases(path: Path) -> set[FailedCase]:
    root = ET.parse(path).getroot()
    failures: set[FailedCase] = set()
    for case in root.iter("testcase"):
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        if case.find("failure") is not None:
            failures.add(FailedCase(classname, name, "failure"))
        if case.find("error") is not None:
            failures.add(FailedCase(classname, name, "error"))
    return failures


def _summary(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    keys = ("tests", "failures", "errors", "skipped")
    return {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in keys
    }


def compare(baseline: Path, head: Path) -> tuple[set[FailedCase], set[FailedCase]]:
    baseline_failures = _failed_cases(baseline)
    head_failures = _failed_cases(head)
    return head_failures - baseline_failures, baseline_failures - head_failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("head", type=Path)
    args = parser.parse_args()

    for path in (args.baseline, args.head):
        if not path.is_file():
            parser.error(f"JUnit file not found: {path}")

    new_failures, resolved_failures = compare(args.baseline, args.head)
    baseline_summary = _summary(args.baseline)
    head_summary = _summary(args.head)

    print(f"baseline summary: {baseline_summary}")
    print(f"head summary:     {head_summary}")
    print(f"baseline failure debt: {baseline_summary['failures'] + baseline_summary['errors']}")

    if resolved_failures:
        print(f"resolved failures ({len(resolved_failures)}):")
        for case in sorted(resolved_failures):
            print(f"  - {case.id}")

    if new_failures:
        print(f"NEW regressions ({len(new_failures)}):", file=sys.stderr)
        for case in sorted(new_failures):
            print(f"  - {case.id}", file=sys.stderr)
        return 1

    print("regression delta: PASS (no head-only failures/errors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
