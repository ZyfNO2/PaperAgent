from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.assert_coverage_threshold import assert_coverage
from scripts.assert_junit_no_skips import assert_no_skips


def test_raw_coverage_threshold_does_not_round_up(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps({"totals": {"percent_covered": 89.9999}}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="below required"):
        assert_coverage(report, 90.0)


def test_junit_skip_is_a_required_integration_failure(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite tests="1" skipped="1"/></testsuites>',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="skipped 1"):
        assert_no_skips(report)
