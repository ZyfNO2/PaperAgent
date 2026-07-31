from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

import pytest

from paperagent.academic.factory import (
    PaperClawDependencyError,
    PaperClawVersionError,
    _check_capabilities,
    _check_paperclaw_available,
    _check_schema_version,
    create_paperclaw_artifact_sink,
    create_paperclaw_evidence_source,
)
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


def test_factory_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> ModuleType:
        raise ImportError(name)

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(PaperClawDependencyError, match="not installed"):
        _check_paperclaw_available()


@pytest.mark.parametrize("version", [None, "academic.v0", "academic.v2"])
def test_factory_rejects_missing_or_incompatible_schema(
    monkeypatch: pytest.MonkeyPatch,
    version: str | None,
) -> None:
    academic = ModuleType("paperclaw.academic")
    if version is not None:
        academic.ACADEMIC_SCHEMA_VERSION = version  # type: ignore[attr-defined]
    monkeypatch.setattr(importlib, "import_module", lambda name: academic)
    with pytest.raises(PaperClawVersionError):
        _check_schema_version()


def test_factory_builds_evidence_and_artifact_adapters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime = object()

    class RuntimeFactory:
        @staticmethod
        def for_workspace(workspace, project_id):
            assert workspace == tmp_path
            assert project_id == "project-1"
            return runtime

    academic = SimpleNamespace(
        ACADEMIC_SCHEMA_VERSION="academic.v1",
        AcademicRuntime=RuntimeFactory,
        EvidenceBundle=object,
        EvidenceLocator=object,
    )
    store = object()

    class StoreFactory:
        def __new__(cls, path):
            assert path == tmp_path / ".paperclaw" / "artifacts"
            return store

    artifacts = SimpleNamespace(FileArtifactStore=StoreFactory)

    def load(name: str):
        if name == "paperclaw.academic":
            return academic
        if name == "paperclaw.artifacts":
            return artifacts
        raise ImportError(name)

    monkeypatch.setattr(importlib, "import_module", load)
    evidence = create_paperclaw_evidence_source(tmp_path, "project-1")
    sink = create_paperclaw_artifact_sink(tmp_path)
    assert evidence.runtime is runtime
    assert sink.store is store
