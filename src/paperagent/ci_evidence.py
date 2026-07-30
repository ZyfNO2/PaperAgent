"""Assertions used to make CI evidence machine-verifiable."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


def assert_coverage(path: Path, threshold: float) -> float:
    payload = json.loads(path.read_text(encoding="utf-8"))
    actual = float(payload["totals"]["percent_covered"])
    if actual < threshold:
        raise SystemExit(f"raw coverage {actual:.12f}% is below required {threshold:.12f}%")
    print(f"raw coverage {actual:.12f}% >= {threshold:.12f}%")
    return actual


def assert_no_skips(path: Path) -> None:
    root = ET.parse(path).getroot()
    skipped = sum(
        int(suite.attrib.get("skipped", "0"))
        for suite in ([root] if root.tag == "testsuite" else root.findall("testsuite"))
    )
    if skipped:
        raise SystemExit(f"required integration suite skipped {skipped} test(s)")
