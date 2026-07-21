from __future__ import annotations

from pathlib import Path

ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")
ANCHOR_TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")


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


def main() -> int:
    replace_once(
        ADAPTER_TEST,
        '''    _looks_like_dataset_name,
    _quoted_title,
''',
        '''    _looks_like_dataset_name,
    _query_seeks_baseline_role,
    _quoted_title,
''',
        "role helper import",
    )
    append_once(
        ADAPTER_TEST,
        "test_explicit_baseline_role_queries_are_propagated",
        '''


def test_explicit_baseline_role_queries_are_propagated() -> None:
    assert _query_seeks_baseline_role("task-matched baseline implementation")
    assert _query_seeks_baseline_role("strong comparator under matched compute")
    assert _query_seeks_baseline_role("retrieve a reproducible comparison method")
    assert not _query_seeks_baseline_role("analyze the failure mechanism")

    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-baseline-role",
        gap_id="g-baseline-role",
        query="task-matched baseline implementation comparison",
        source_types=["paper"],
    )
    candidate = adapter._candidate(
        query,
        _paper("A Reproducible Task-Matched Comparator"),
        False,
        relation="baseline_role_query",
    )
    assert candidate.metadata["relation"] == "baseline_role_query"
    assert candidate.metadata["baseline_candidate"] == "inferred"
''',
    )
    append_once(
        ANCHOR_TEST,
        "test_explicit_baseline_role_query_outranks_dataset_parallel_candidate",
        '''


def test_explicit_baseline_role_query_outranks_dataset_parallel_candidate() -> None:
    role_query = _item(
        "role-query",
        "A Reproducible Baseline Returned by a Baseline Query",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "baseline_role_query",
            "rank_score": "0.70",
        },
    )
    dataset_parallel = _item(
        "dataset-parallel",
        "A Higher Scoring Dataset-Parallel Method",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.95",
        },
    )
    selected = _select_inferred_baseline_evidence((dataset_parallel, role_query))
    assert selected is not None
    assert selected.evidence_id == "role-query"
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
