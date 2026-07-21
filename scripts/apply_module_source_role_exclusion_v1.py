from __future__ import annotations

from pathlib import Path

METHOD = Path("src/paperagent/method_design_draft.py")
TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")


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
        METHOD,
        '''    papers = tuple(item for item in candidates if item.source_type == "paper")
    if not papers:
        return None
''',
        '''    papers = tuple(
        item
        for item in candidates
        if item.source_type == "paper"
        and item.metadata.get("comparator_candidate") != "inferred"
        and item.metadata.get("relation") != "comparator_role_query"
    )
    if not papers:
        return None
''',
        "exclude comparator candidates from module sources",
    )
    append_once(
        TEST,
        "test_comparator_candidate_is_not_selected_as_module_source",
        '''


def test_comparator_candidate_is_not_selected_as_module_source() -> None:
    baseline = _item(
        "baseline-module-source",
        "A Task-Matched Baseline and Mechanism Paper",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.70",
            "license": "CC BY 4.0",
        },
    )
    comparator = _item(
        "comparator-not-module",
        "A Strong Independent Comparator",
        metadata={
            "comparator_candidate": "inferred",
            "relation": "comparator_role_query",
            "rank_score": "0.99",
        },
    )
    selected = _select_module_evidence((baseline, comparator), baseline=baseline)
    assert selected is not None
    assert selected.evidence_id == baseline.evidence_id
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
