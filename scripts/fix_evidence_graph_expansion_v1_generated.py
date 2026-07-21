from __future__ import annotations

from pathlib import Path


METHOD = Path("src/paperagent/method_design_draft.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old in source:
        return source.replace(old, new, 1)
    if new in source:
        return source
    raise RuntimeError(f"missing generated repair target: {label}")


def main() -> int:
    source = METHOD.read_text(encoding="utf-8")
    source = replace_once(
        source,
        (
            '                        f"review source {primary.stable_identifier}; '
            'implementation baseline unresolved"\n'
        ),
        (
            '                        (\n'
            '                            f"review source {primary.stable_identifier}; "\n'
            '                            "implementation baseline unresolved"\n'
            '                        )\n'
        ),
        "inferred baseline review wrapping",
    )
    source = replace_once(
        source,
        '''def _select_inferred_baseline_evidence(
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    papers = tuple(item for item in candidates if item.source_type == "paper")
    return max(papers, key=_baseline_evidence_rank, default=None)
''',
        '''def _select_inferred_baseline_evidence(
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    papers = tuple(item for item in candidates if item.source_type == "paper")
    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)
''',
        "mypy-safe inferred baseline selection",
    )
    source = replace_once(
        source,
        (
            '        "no public dataset is required at discovery time; use task-appropriate '
            'user-owned, "\n'
        ),
        (
            '        "unresolved task-matched data source; no public dataset is required at "\n'
            '        "discovery time; use task-appropriate user-owned, "\n'
        ),
        "optional unresolved data source semantics",
    )
    METHOD.write_text(source, encoding="utf-8")

    test_source = ADAPTER_TEST.read_text(encoding="utf-8")
    test_source = replace_once(
        test_source,
        '        _paper("A verified MIMII benchmark paper"),\n',
        '        _paper("A verified industrial evaluation paper"),\n',
        "focused dataset relation fixture",
    )
    ADAPTER_TEST.write_text(test_source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
