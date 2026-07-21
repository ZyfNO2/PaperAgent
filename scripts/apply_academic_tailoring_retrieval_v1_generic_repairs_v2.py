from __future__ import annotations

from pathlib import Path


PLANNING_PATH = Path("src/paperagent/nodes/planning.py")
INTAKE_TEST_PATH = Path("tests/nodes/test_intake_planning.py")
NONBLOCKING_TEST_PATH = Path("tests/nodes/test_planning_nonblocking.py")


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    if old in source:
        return source.replace(old, new, 1)
    if new in source:
        return source
    raise RuntimeError(f"{label} block not found")


def _patch_planning_without_extra_queries() -> None:
    source = PLANNING_PATH.read_text(encoding="utf-8")

    helper_start = source.find("\n\ndef _ensure_public_asset_discovery_query(")
    if helper_start >= 0:
        helper_end = source.find("\n\nasync def planning_node(", helper_start)
        if helper_end < 0:
            raise RuntimeError("public asset helper end marker not found")
        source = source[:helper_start] + source[helper_end:]

    with_assets = '''    if result is not None:
        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        with_assets = _ensure_public_asset_discovery_query(
            with_materials,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_assets)
'''
    without_assets = '''    if result is not None:
        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_materials)
'''
    source = _replace_once(
        source,
        with_assets,
        without_assets,
        label="planning result normalization",
    )

    old_runtime = '''def _runtime_source_types(query: SearchQuery) -> SearchQuery:
    """Add the configured public-web lane for repository and dataset discovery.

    Scholarly metadata APIs do not index arbitrary repository or dataset landing pages. The
    Web lane remains supplemental and is still subject to source-policy precision checks.
    """

    source_types = list(query.source_types)
    if {"repository", "dataset"}.intersection(source_types) and "web" not in source_types:
        source_types.append("web")
    if source_types == query.source_types:
        return query
    return query.model_copy(update={"source_types": source_types})
'''
    new_runtime = '''_PUBLIC_ASSET_QUERY_HINTS = (
    "baseline",
    "reproducible",
    "reproduction",
    "implementation",
    "repository",
    "code",
    "dataset",
    "基线",
    "复现",
    "实现",
    "代码",
    "数据集",
)


def _runtime_source_types(query: SearchQuery) -> SearchQuery:
    """Extend an existing baseline query with public code/data lanes without adding queries."""

    source_types = list(query.source_types)
    query_text = f"{query.gap_id} {query.query}".casefold()
    if any(hint in query_text for hint in _PUBLIC_ASSET_QUERY_HINTS):
        for source_type in ("repository", "dataset"):
            if source_type not in source_types:
                source_types.append(source_type)
    if {"repository", "dataset"}.intersection(source_types) and "web" not in source_types:
        source_types.append("web")
    if source_types == query.source_types:
        return query
    return query.model_copy(update={"source_types": source_types})
'''
    source = _replace_once(source, old_runtime, new_runtime, label="runtime source types")
    PLANNING_PATH.write_text(source, encoding="utf-8")


def _update_tests() -> None:
    intake_tests = INTAKE_TEST_PATH.read_text(encoding="utf-8")
    obsolete_marker = "\n\ndef test_public_asset_discovery_adds_one_generic_code_and_data_lane() -> None:\n"
    if obsolete_marker in intake_tests:
        intake_tests = intake_tests.split(obsolete_marker, 1)[0].rstrip() + "\n"

    replacement_test = r'''


def test_plan_normalization__baseline_query_adds_asset_lanes_without_extra_query() -> None:
    from paperagent.nodes.planning import _normalize_plan_to_query_budget
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="few-shot scientific classification",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="baseline", description="find a baseline")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="baseline",
                query="reproducible classification baseline",
                source_types=["paper"],
            )
        ],
    )

    normalized = _normalize_plan_to_query_budget(plan, query_budget=10)

    assert len(normalized.search_queries) == 1
    assert normalized.search_queries[0].source_types == [
        "paper",
        "repository",
        "dataset",
        "web",
    ]
'''
    if "test_plan_normalization__baseline_query_adds_asset_lanes_without_extra_query" not in intake_tests:
        intake_tests += replacement_test
    INTAKE_TEST_PATH.write_text(intake_tests, encoding="utf-8")

    nonblocking_tests = NONBLOCKING_TEST_PATH.read_text(encoding="utf-8")
    old_assertions = '''    assert normalized.status == "ready"
    assert len(normalized.evidence_gaps) == 2
    assert len(normalized.search_queries) == 2
    assert normalized.evidence_gaps[0].gap_id == "user-material-01-identity"
    assert normalized.evidence_gaps[0].minimum_accepted_items == 1
    assert normalized.search_queries[0].query == (
        "LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation"
    )
    assert normalized.search_queries[0].gap_id == normalized.evidence_gaps[0].gap_id
'''
    new_assertions = '''    assert normalized.status == "ready"
    assert len(normalized.evidence_gaps) == 2
    assert len(normalized.search_queries) == 3
    assert normalized.evidence_gaps[0].gap_id == "user-material-01-identity"
    assert normalized.evidence_gaps[0].minimum_accepted_items == 1
    assert normalized.search_queries[0].query == (
        '"LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation"'
    )
    assert normalized.search_queries[0].source_types == ["paper", "web"]
    assert normalized.search_queries[1].query == (
        '"LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation" '
        "official implementation code repository"
    )
    assert normalized.search_queries[1].source_types == ["repository", "web"]
    assert normalized.search_queries[0].gap_id == normalized.evidence_gaps[0].gap_id
    assert normalized.search_queries[1].gap_id == normalized.evidence_gaps[0].gap_id
'''
    nonblocking_tests = _replace_once(
        nonblocking_tests,
        old_assertions,
        new_assertions,
        label="supplied title assertions",
    )
    NONBLOCKING_TEST_PATH.write_text(nonblocking_tests, encoding="utf-8")


def main() -> int:
    _patch_planning_without_extra_queries()
    _update_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
