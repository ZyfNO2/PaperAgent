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
        '''def _select_reported_comparator_evidence(
    value: str | None,
    accepted: tuple[EvidenceItem, ...],
    *,
    excluded_ids: set[str],
) -> EvidenceItem | None:
    if value is None or not value.strip():
        return None
    for item in accepted:
        if (
            item.source_type == "paper"
            and item.evidence_id not in excluded_ids
            and not _is_review_evidence(item.title, item.summary)
            and _titles_equivalent(item.title, value.strip())
        ):
            return item
    return None
''',
        "reported comparator exclusions",
    )
    replace_once(
        METHOD,
        '''    reported_comparator_evidence = _select_reported_comparator_evidence(
        draft.reported_comparator,
        accepted,
    )
''',
        '''    excluded_comparator_ids = {module_primary.evidence_id}
    if baseline_evidence is not None:
        excluded_comparator_ids.add(baseline_evidence.evidence_id)
    reported_comparator_evidence = _select_reported_comparator_evidence(
        draft.reported_comparator,
        accepted,
        excluded_ids=excluded_comparator_ids,
    )
''',
        "call reported comparator with exclusions",
    )
    replace_once(
        METHOD,
        '''        excluded_ids = {module_primary.evidence_id}
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
        '''        comparator_evidence = _select_inferred_comparator_evidence(
            attributed,
            excluded_ids=excluded_comparator_ids,
        )
        if comparator_evidence is not None:
            grounded_comparator = comparator_evidence.title
            comparator_evidence_id = comparator_evidence.evidence_id
''',
        "remove arbitrary comparator fallback",
    )
    append_once(
        TEST,
        "test_baseline_or_module_evidence_cannot_be_reused_as_comparator",
        '''


def test_baseline_or_module_evidence_cannot_be_reused_as_comparator() -> None:
    state = _state()
    proposal = build_method_proposal(
        state,
        _draft(
            comparison_readiness_confirmed=True,
            reported_comparator=(
                "Drone-DETR: Efficient Small Object Detection for Remote Sensing Image"
            ),
        ),
    )
    assert all(
        experiment.arm_type is not ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )


def test_unmarked_neighbor_paper_is_not_used_as_comparator_fallback() -> None:
    state = _state()
    evidence = state["evidence"]
    assert evidence is not None
    neighbor_id = "ev-unmarked-neighbor"
    neighbor = EvidenceItem(
        evidence_id=neighbor_id,
        source_type="paper",
        title="A Related Detection Study",
        locator="doi:10.1000/related-detection",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary="A related study without an explicit comparator retrieval role.",
        content_hash="sha256:related-detection",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/related-detection",
            "relation": "direct_query",
            "rank_score": "0.99",
        },
    )
    neighbor_state = cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(
                update={
                    "items": [*evidence.items, neighbor],
                    "accepted_ids": [*evidence.accepted_ids, neighbor_id],
                    "identity_verified_ids": [
                        *evidence.identity_verified_ids,
                        neighbor_id,
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
        neighbor_state,
        _draft(comparison_readiness_confirmed=True),
    )
    assert all(
        experiment.arm_type is not ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
