from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.runner import load_cases
from evaluation.schemas import EvaluationCase


def test_case_defaults_and_validation() -> None:
    case = EvaluationCase(case_id="case_001", category="search", input="question")
    assert case.max_steps == 12
    assert case.mode == "offline"
    with pytest.raises(ValidationError):
        EvaluationCase(
            case_id="bad",
            category="x",
            input="x",
            required_tools=("search",),
            forbidden_tools=("search",),
        )


def test_required_tools_must_be_allowed() -> None:
    with pytest.raises(ValidationError, match="subset"):
        EvaluationCase(
            case_id="bad_002",
            category="x",
            input="x",
            required_tools=("fetch",),
            allowed_tools=("search",),
        )


def test_invalid_jsonl_fails_before_execution(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"case_id":"x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid evaluation case"):
        load_cases(path)


def test_duplicate_case_id_fails(tmp_path: Path) -> None:
    line = '{"case_id":"duplicate_001","category":"x","input":"x"}\n'
    path = tmp_path / "duplicate.jsonl"
    path.write_text(line + line, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_cases(path)


def test_all_versioned_datasets_load_and_contain_twenty_cases() -> None:
    root = Path("evaluation/cases")
    cases = tuple(case for path in sorted(root.glob("*.jsonl")) for case in load_cases(path))
    assert len(cases) == 20
    assert len({case.case_id for case in cases}) == 20
    assert {case.mode for case in cases} == {"offline", "live"}
