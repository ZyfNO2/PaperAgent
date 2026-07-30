from __future__ import annotations

from types import ModuleType

import pytest

from paperagent.academic.factory import PaperClawVersionError, _check_capabilities
from paperagent.academic.planner import (
    AcademicQueryDecomposition,
    AcademicSubQuery,
    decompose_question,
)


def test_identity_planner_round_trips_and_preserves_doi() -> None:
    plan = decompose_question("Compare results for 10.1234/Example", paper_ids=("a", "b"))
    restored = AcademicQueryDecomposition.from_dict(plan.to_dict())
    assert restored == plan
    assert restored.sub_queries[0].identity_constraints == ("10.1234/Example",)
    assert "10.1234/Example" in restored.sub_queries[0].rewritten_query


def test_planner_fans_out_cross_paper_comparison_deterministically() -> None:
    first = decompose_question("compare baseline accuracy", paper_ids=("b", "a"))
    second = decompose_question("compare baseline accuracy", paper_ids=("b", "a"))
    assert first == second
    assert [item.paper_ids for item in first.sub_queries] == [("b",), ("a",), ("b", "a")]


@pytest.mark.parametrize(
    "field,value",
    [("result_budget", 0), ("result_budget", 101), ("character_budget", 0), ("token_budget", 0)],
)
def test_planner_rejects_invalid_budget_boundaries(field: str, value: int) -> None:
    values = {field: value}
    with pytest.raises(ValueError):
        AcademicSubQuery("sq", "method", "query", **values)


def test_planner_rejects_identity_losing_rewrite() -> None:
    with pytest.raises(ValueError, match="identity"):
        AcademicSubQuery("sq", "identity", "different", identity_constraints=("10.1/x",))


def test_factory_capability_check_fails_closed() -> None:
    module = ModuleType("paperclaw.academic")
    module.AcademicRuntime = object  # type: ignore[attr-defined]
    with pytest.raises(PaperClawVersionError, match="EvidenceBundle, EvidenceLocator"):
        _check_capabilities(module, "AcademicRuntime", "EvidenceBundle", "EvidenceLocator")
