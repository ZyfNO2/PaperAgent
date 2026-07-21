from __future__ import annotations

from pathlib import Path

ADAPTER = Path("src/paperagent/literature/adapter.py")
METHOD = Path("src/paperagent/method_design_draft.py")
PLANNING = Path("src/paperagent/nodes/planning.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")
ANCHOR_TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")
PLANNING_TEST = Path("tests/nodes/test_intake_planning.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{path}: missing {label}")
    path.write_text(source, encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    source = path.read_text(encoding="utf-8")
    if marker not in source:
        source += addition
    path.write_text(source, encoding="utf-8")


def patch_adapter() -> None:
    replace_once(
        ADAPTER,
        '''_BASELINE_ROLE_QUERY = re.compile(
    r"(?:\\bbaselines?\\b|\\bcomparators?\\b|\\bcomparison\\b|基线|对照|比较|对比)",
    re.IGNORECASE,
)
''',
        '''_BASELINE_ROLE_QUERY = re.compile(r"(?:\\bbaselines?\\b|基线)", re.IGNORECASE)
_COMPARATOR_ROLE_QUERY = re.compile(
    r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
    re.IGNORECASE,
)
''',
        "split query-role patterns",
    )
    replace_once(
        ADAPTER,
        '''def _query_seeks_baseline_role(query: str) -> bool:
    return bool(_BASELINE_ROLE_QUERY.search(query))


def _identity_tokens(value: str) -> tuple[str, ...]:
''',
        '''def _query_seeks_baseline_role(query: str) -> bool:
    return bool(_BASELINE_ROLE_QUERY.search(query))


def _query_seeks_comparator_role(query: str) -> bool:
    return not _query_seeks_baseline_role(query) and bool(_COMPARATOR_ROLE_QUERY.search(query))


def _query_candidate_role(query: str) -> str | None:
    if _query_seeks_baseline_role(query):
        return "baseline"
    if _query_seeks_comparator_role(query):
        return "comparator"
    return None


def _identity_tokens(value: str) -> tuple[str, ...]:
''',
        "query role helpers",
    )
    replace_once(
        ADAPTER,
        '''                    else (
                        "baseline_role_query"
                        if _query_seeks_baseline_role(query.query)
                        else "direct_query"
                    )
''',
        '''                    else (
                        "baseline_role_query"
                        if _query_candidate_role(query.query) == "baseline"
                        else (
                            "comparator_role_query"
                            if _query_candidate_role(query.query) == "comparator"
                            else "direct_query"
                        )
                    )
''',
        "role-specific evidence relation",
    )
    replace_once(
        ADAPTER,
        '''                **(
                    {"baseline_candidate": "declared"}
                    if relation == "declared_identity"
                    else (
                        {"baseline_candidate": "inferred"}
                        if relation in {"parallel_via_dataset", "baseline_role_query"}
                        else {}
                    )
                ),
''',
        '''                **(
                    {"baseline_candidate": "declared"}
                    if relation == "declared_identity"
                    else (
                        {"baseline_candidate": "inferred"}
                        if relation in {"parallel_via_dataset", "baseline_role_query"}
                        else (
                            {"comparator_candidate": "inferred"}
                            if relation == "comparator_role_query"
                            else {}
                        )
                    )
                ),
''',
        "separate candidate markers",
    )


def patch_method() -> None:
    replace_once(
        METHOD,
        '''def _select_primary_evidence(
''',
        '''def _comparator_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
    if item.source_type != "paper":
        return (-1, -1.0, item.evidence_id)
    marker_rank = int(item.metadata.get("comparator_candidate") == "inferred")
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (marker_rank, rank_score, item.evidence_id)


def _select_inferred_comparator_evidence(
    candidates: tuple[EvidenceItem, ...],
    *,
    excluded_ids: set[str],
) -> EvidenceItem | None:
    papers = tuple(
        item
        for item in candidates
        if item.source_type == "paper"
        and item.evidence_id not in excluded_ids
        and item.metadata.get("comparator_candidate") == "inferred"
        and item.metadata.get("relation") == "comparator_role_query"
    )
    if not papers:
        return None
    return max(papers, key=_comparator_evidence_rank)


def _select_primary_evidence(
''',
        "comparator selector",
    )
    replace_once(
        METHOD,
        '''    if draft.comparison_readiness_confirmed and (
        grounded_comparator is None or comparator_evidence_id is None
    ):
        excluded_ids = {module_primary.evidence_id}
        if baseline_evidence is not None:
            excluded_ids.add(baseline_evidence.evidence_id)
        for item in attributed:
            if item.evidence_id in excluded_ids:
                continue
            grounded_comparator = item.title
            comparator_evidence_id = item.evidence_id
            break
''',
        '''    if draft.comparison_readiness_confirmed and (
        grounded_comparator is None or comparator_evidence_id is None
    ):
        excluded_ids = {module_primary.evidence_id}
        if baseline_evidence is not None:
            excluded_ids.add(baseline_evidence.evidence_id)
        comparator_evidence = _select_inferred_comparator_evidence(
            attributed,
            excluded_ids=excluded_ids,
        )
        if comparator_evidence is not None:
            grounded_comparator = comparator_evidence.title
            comparator_evidence_id = comparator_evidence.evidence_id
        else:
            for item in attributed:
                if item.evidence_id in excluded_ids:
                    continue
                grounded_comparator = item.title
                comparator_evidence_id = item.evidence_id
                break
''',
        "prefer explicit comparator candidates",
    )


def patch_planning() -> None:
    replace_once(
        PLANNING,
        '''_BASELINE_ROLE_HINTS = (
    "baseline",
    "comparator",
    "comparison",
    "基线",
    "对照",
    "比较",
    "对比",
)
''',
        '''_BASELINE_ROLE_HINTS = (
    "baseline",
    "基线",
)
''',
        "baseline-only planning hints",
    )
    replace_once(
        PLANNING,
        '''    "No explicit baseline/comparator evidence gap was declared; baseline discovery remains "
''',
        '''    "No explicit development-baseline evidence gap was declared; baseline discovery remains "
''',
        "development baseline risk wording",
    )


def patch_tests() -> None:
    replace_once(
        ADAPTER_TEST,
        '''    _looks_like_dataset_name,
    _query_seeks_baseline_role,
''',
        '''    _looks_like_dataset_name,
    _query_candidate_role,
    _query_seeks_baseline_role,
    _query_seeks_comparator_role,
''',
        "role helper imports",
    )
    append_once(
        ADAPTER_TEST,
        "test_baseline_and_comparator_queries_have_distinct_roles",
        '''


def test_baseline_and_comparator_queries_have_distinct_roles() -> None:
    assert _query_candidate_role("reproducible development baseline") == "baseline"
    assert _query_candidate_role("strong comparator under matched compute") == "comparator"
    assert _query_candidate_role("comparison against recent methods") == "comparator"
    assert _query_candidate_role("failure mechanism analysis") is None
    assert _query_seeks_baseline_role("基线复现")
    assert _query_seeks_comparator_role("强模型对比")

    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-comparator-role",
        gap_id="g-comparator-role",
        query="strong comparator under matched compute",
        source_types=["paper"],
    )
    candidate = adapter._candidate(
        query,
        _paper("A Strong Matched Comparator"),
        False,
        relation="comparator_role_query",
    )
    assert candidate.metadata["comparator_candidate"] == "inferred"
    assert "baseline_candidate" not in candidate.metadata
''',
    )
    replace_once(
        ADAPTER_TEST,
        '''    assert _query_seeks_baseline_role("strong comparator under matched compute")
    assert _query_seeks_baseline_role("retrieve a reproducible comparison method")
''',
        '''    assert not _query_seeks_baseline_role("strong comparator under matched compute")
    assert not _query_seeks_baseline_role("retrieve a reproducible comparison method")
''',
        "existing role expectations",
    )
    append_once(
        ANCHOR_TEST,
        "test_comparator_role_candidate_is_not_eligible_as_baseline",
        '''


def test_comparator_role_candidate_is_not_eligible_as_baseline() -> None:
    comparator = _item(
        "strong-comparator",
        "A Strong Comparator",
        metadata={
            "comparator_candidate": "inferred",
            "relation": "comparator_role_query",
            "rank_score": "0.99",
        },
    )
    assert _select_inferred_baseline_evidence((comparator,)) is None
''',
    )
    append_once(
        PLANNING_TEST,
        "test_comparator_only_gap_does_not_become_development_baseline_query",
        '''


def test_comparator_only_gap_does_not_become_development_baseline_query() -> None:
    from paperagent.nodes.planning import (
        _BASELINE_QUERY_ABSENT_RISK,
        _ensure_baseline_role_query,
    )
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    query = SearchQuery(
        query_id="q-comparator",
        gap_id="strong-comparator",
        query="strong comparator comparison under matched compute",
        source_types=["paper"],
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="task",
        scope="test",
        evidence_gaps=[
            EvidenceGap(gap_id="strong-comparator", description="strong comparison evidence")
        ],
        search_queries=[query],
    )
    updated = _ensure_baseline_role_query(plan, query_budget=10)
    assert updated.search_queries == [query]
    assert _BASELINE_QUERY_ABSENT_RISK in updated.risks
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
