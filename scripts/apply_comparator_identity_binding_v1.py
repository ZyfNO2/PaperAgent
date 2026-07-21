from __future__ import annotations

from pathlib import Path

METHOD = Path("src/paperagent/method_design_draft.py")
TEST = Path("tests/methodology/test_method_design_draft.py")


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
        '''def _grounded_evidence_id(value: str | None, accepted: tuple[EvidenceItem, ...]) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if not normalized:
        return None
    for item in accepted:
        title = getattr(item, "title", "")
        summary = getattr(item, "summary", "")
        if normalized in f"{title}\n{summary}".casefold():
            return item.evidence_id
    return None
''',
        '''def _select_reported_comparator_evidence(
    value: str | None,
    accepted: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    if value is None or not value.strip():
        return None
    for item in accepted:
        if (
            item.source_type == "paper"
            and not _is_review_evidence(item.title, item.summary)
            and _titles_equivalent(item.title, value.strip())
        ):
            return item
    return None
''',
        "strict reported comparator identity binding",
    )
    replace_once(
        METHOD,
        '''    grounded_comparator = _grounded_optional(draft.reported_comparator, evidence_text)
    comparator_evidence_id = _grounded_evidence_id(grounded_comparator, accepted)
''',
        '''    reported_comparator_evidence = _select_reported_comparator_evidence(
        draft.reported_comparator,
        accepted,
    )
    grounded_comparator = (
        reported_comparator_evidence.title
        if reported_comparator_evidence is not None
        else None
    )
    comparator_evidence_id = (
        reported_comparator_evidence.evidence_id
        if reported_comparator_evidence is not None
        else None
    )
''',
        "reported comparator use",
    )
    replace_once(
        TEST,
        '''    assert arm_types == {
        ExperimentArmType.BASELINE,
        ExperimentArmType.SINGLE_MODULE,
        ExperimentArmType.FULL,
        ExperimentArmType.STRONG_COMPARISON,
    }
''',
        '''    assert arm_types == {
        ExperimentArmType.BASELINE,
        ExperimentArmType.SINGLE_MODULE,
        ExperimentArmType.FULL,
    }
''',
        "summary mention no longer creates comparator arm",
    )
    append_once(
        TEST,
        "test_reported_comparator_requires_independent_paper_identity",
        '''


def test_reported_comparator_requires_independent_paper_identity() -> None:
    state = _state()
    proposal = build_method_proposal(
        state,
        _draft(comparison_readiness_confirmed=True),
    )
    assert all(
        experiment.arm_type is not ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )


def test_independent_comparator_paper_creates_strong_comparison_arm() -> None:
    state = _state()
    evidence = state["evidence"]
    assert evidence is not None
    comparator_id = "ev-rt-detr-r18"
    comparator_item = EvidenceItem(
        evidence_id=comparator_id,
        source_type="paper",
        title="RT-DETR-R18",
        locator="doi:10.1000/rt-detr-r18",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary=(
            "RT-DETR-R18 is a task-matched detector comparison with a documented "
            "paper identity."
        ),
        content_hash="sha256:rt-detr-r18",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/rt-detr-r18",
            "comparator_candidate": "inferred",
            "relation": "comparator_role_query",
            "rank_score": "0.95",
        },
    )
    comparator_state = cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(
                update={
                    "items": [*evidence.items, comparator_item],
                    "accepted_ids": [*evidence.accepted_ids, comparator_id],
                    "identity_verified_ids": [
                        *evidence.identity_verified_ids,
                        comparator_id,
                    ],
                    "coverage_by_gap": {
                        **evidence.coverage_by_gap,
                        "baseline_comparison": (
                            evidence.coverage_by_gap.get("baseline_comparison", 0) + 1
                        ),
                    },
                }
            ),
        },
    )
    proposal = build_method_proposal(
        comparator_state,
        _draft(comparison_readiness_confirmed=True),
    )
    strong = [
        experiment
        for experiment in proposal.methodology_plan.experiments
        if experiment.arm_type is ExperimentArmType.STRONG_COMPARISON
    ]
    assert len(strong) == 1
    assert strong[0].comparator == "RT-DETR-R18"
    assert strong[0].source_evidence_id == comparator_id
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
