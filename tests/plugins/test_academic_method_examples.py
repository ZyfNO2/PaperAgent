from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from paperagent.plugins.academic_method import MethodPlan, audit_method_plan

_EXAMPLES = Path("examples/v0_8")


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


@pytest.mark.parametrize(
    "filename",
    ("go-plan.json", "revise-plan.json", "no-go-plan.json"),
)
def test_committed_method_examples_match_expected_verdicts(filename: str) -> None:
    expected = _load_object(_EXAMPLES / "expected-verdicts.json")[filename]
    assert isinstance(expected, dict)
    report = audit_method_plan(MethodPlan.model_validate(_load_object(_EXAMPLES / filename)))

    assert report.verdict.value == expected["verdict"]
    assert sorted(check.check_id for check in report.checks if not check.passed) == sorted(
        expected["failed_check_ids"]
    )
