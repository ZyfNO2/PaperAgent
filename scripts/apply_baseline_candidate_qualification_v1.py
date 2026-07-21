from __future__ import annotations

from pathlib import Path

ADAPTER = Path("src/paperagent/literature/adapter.py")
METHOD = Path("src/paperagent/method_design_draft.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")
ANCHOR_TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")
METHOD_TEST = Path("tests/methodology/test_method_design_draft.py")


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
        '''                "relation": relation,
                "baseline_candidate": (
                    "declared" if relation == "declared_identity" else "inferred"
                ),
                "rank_score": f"{score:.6f}",
''',
        '''                "relation": relation,
                **(
                    {"baseline_candidate": "declared"}
                    if relation == "declared_identity"
                    else (
                        {"baseline_candidate": "inferred"}
                        if relation == "parallel_via_dataset"
                        else {}
                    )
                ),
                "rank_score": f"{score:.6f}",
''',
        "qualified baseline candidate metadata",
    )


def patch_method() -> None:
    replace_once(
        METHOD,
        '''def _baseline_evidence_rank(item: EvidenceItem) -> tuple[int, int, float, str]:
    if item.source_type != "paper":
        return (-1, -1, -1.0, item.evidence_id)
    marker = item.metadata.get("baseline_candidate", "")
    relation = item.metadata.get("relation", "")
    marker_rank = {"declared": 3, "inferred": 2}.get(marker, 1)
    relation_rank = {
        "declared_identity": 3,
        "parallel_via_dataset": 2,
        "direct_query": 1,
    }.get(relation, 0)
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (marker_rank, relation_rank, rank_score, item.evidence_id)


def _select_inferred_baseline_evidence(
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    papers = tuple(item for item in candidates if item.source_type == "paper")
    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)


def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    declared = _select_declared_baseline_evidence(references, candidates)
    return declared or _select_inferred_baseline_evidence(candidates) or candidates[0]
''',
        '''def _baseline_evidence_rank(item: EvidenceItem) -> tuple[int, int, float, str]:
    if item.source_type != "paper":
        return (-1, -1, -1.0, item.evidence_id)
    marker = item.metadata.get("baseline_candidate", "")
    relation = item.metadata.get("relation", "")
    marker_rank = {"declared": 3, "inferred": 2}.get(marker, 0)
    relation_rank = {
        "declared_identity": 3,
        "parallel_via_dataset": 2,
    }.get(relation, 0)
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (marker_rank, relation_rank, rank_score, item.evidence_id)


def _select_inferred_baseline_evidence(
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    papers = tuple(
        item
        for item in candidates
        if item.source_type == "paper"
        and item.metadata.get("baseline_candidate") == "inferred"
        and item.metadata.get("relation") == "parallel_via_dataset"
    )
    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)


def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    selected = _select_declared_baseline_evidence(
        references, candidates
    ) or _select_inferred_baseline_evidence(candidates)
    if selected is None:
        raise ValueError("no evidence-bound baseline candidate is available")
    return selected


def _module_evidence_rank(
    item: EvidenceItem,
    *,
    baseline_evidence_id: str | None,
) -> tuple[int, int, float, str]:
    if item.source_type != "paper":
        return (-1, -1, -1.0, item.evidence_id)
    relation = item.metadata.get("relation", "")
    relation_rank = {
        "direct_query": 3,
        "parallel_via_dataset": 2,
        "declared_identity": 1,
    }.get(relation, 0)
    distinct_from_baseline = int(item.evidence_id != baseline_evidence_id)
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (distinct_from_baseline, relation_rank, rank_score, item.evidence_id)


def _select_module_evidence(
    candidates: tuple[EvidenceItem, ...],
    *,
    baseline: EvidenceItem | None,
) -> EvidenceItem | None:
    papers = tuple(item for item in candidates if item.source_type == "paper")
    if not papers:
        return None
    baseline_id = baseline.evidence_id if baseline is not None else None
    return max(
        papers,
        key=lambda item: _module_evidence_rank(
            item,
            baseline_evidence_id=baseline_id,
        ),
    )
''',
        "baseline qualification and module selection",
    )
    replace_once(
        METHOD,
        '''    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    )
    primary = baseline_evidence or _select_inferred_baseline_evidence(method_evidence)
    if primary is None:
        raise ValueError("method canonicalization requires accepted paper evidence")
    dataset_evidence = _select_dataset_evidence(request.question, accepted)
''',
        '''    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    ) or _select_inferred_baseline_evidence(method_evidence)
    module_primary = _select_module_evidence(method_evidence, baseline=baseline_evidence)
    if module_primary is None:
        raise ValueError("method canonicalization requires accepted paper evidence")
    dataset_evidence = _select_dataset_evidence(request.question, accepted)
''',
        "separate baseline and module evidence",
    )
    replace_once(
        METHOD,
        '''    if draft.comparison_readiness_confirmed and (
        grounded_comparator is None or comparator_evidence_id is None
    ):
        for item in attributed:
            if item.evidence_id == primary.evidence_id:
                continue
            grounded_comparator = item.title
            comparator_evidence_id = item.evidence_id
            break

    readiness_confirmed = (
        draft.baseline_readiness_confirmed
        and draft.evaluation_protocol_validated
        and not draft.explicit_evaluation_protocol_invalid
    )
''',
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

    baseline_identity_resolved = baseline_evidence is not None
    effective_baseline_readiness = (
        draft.baseline_readiness_confirmed and baseline_identity_resolved
    )
    readiness_confirmed = (
        effective_baseline_readiness
        and draft.evaluation_protocol_validated
        and not draft.explicit_evaluation_protocol_invalid
    )
''',
        "effective baseline readiness",
    )
    replace_once(
        METHOD,
        '''    review_primary = _is_review_evidence(primary.title, primary.summary)
    baseline_unresolved = bool(declared_baseline_titles and baseline_evidence is None)
    baseline_name = (
        declared_baseline_titles[0]
        if baseline_unresolved
        else (
            "unresolved task-matched baseline selected from accepted review evidence"
            if review_primary
            else primary.title
        )
    )
    baseline_source_evidence_id = (
        baseline_evidence.evidence_id
        if baseline_evidence is not None
        else (None if baseline_unresolved else primary.evidence_id)
    )
    baseline_inferred = not declared_baseline_titles and baseline_evidence is None
''',
        '''    baseline_unresolved = baseline_evidence is None
    declared_baseline_unresolved = bool(declared_baseline_titles and baseline_unresolved)
    baseline_name = (
        baseline_evidence.title
        if baseline_evidence is not None
        else (
            declared_baseline_titles[0]
            if declared_baseline_titles
            else (
                "unresolved task-matched baseline; retrieve and reproduce an "
                "evidence-bound comparator"
            )
        )
    )
    baseline_source_evidence_id = (
        baseline_evidence.evidence_id if baseline_evidence is not None else None
    )
    baseline_inferred = baseline_evidence is not None and not declared_baseline_titles
''',
        "unresolved baseline semantics",
    )
    replace_once(
        METHOD,
        '''        baseline_readiness_confirmed=draft.baseline_readiness_confirmed,
''',
        '''        baseline_readiness_confirmed=effective_baseline_readiness,
''',
        "contract readiness",
    )
    replace_once(
        METHOD,
        '''        version_or_commit=(
            (
                "declared baseline identity unresolved; do not implement until the exact "
                "paper is verified"
            )
            if baseline_unresolved
            else (
                "user-declared frozen implementation; preserve the exact version or commit"
                if readiness_confirmed
                else (
                    (
                        f"inferred from evidence relation at {primary.stable_identifier}; "
                        "reproduce and freeze an implementation before module integration"
                    )
                    if baseline_inferred
                    else (
                        (
                            f"review source {primary.stable_identifier}; "
                            "implementation baseline unresolved"
                        )
                        if review_primary
                        else (
                            f"published source {primary.stable_identifier}; "
                            "implementation commit unresolved"
                        )
                    )
                )
            )
        ),
        source_evidence_id=baseline_source_evidence_id,
        license=_metadata_text(primary.metadata, "license"),
''',
        '''        version_or_commit=(
            (
                "declared baseline identity unresolved; do not implement until the exact "
                "paper is verified"
            )
            if declared_baseline_unresolved
            else (
                "baseline identity unresolved; retrieve an evidence-bound comparator and "
                "freeze its implementation before integration"
                if baseline_unresolved
                else (
                    "user-declared frozen implementation; preserve the exact version or commit"
                    if readiness_confirmed
                    else (
                        (
                            f"inferred from evidence relation at "
                            f"{baseline_evidence.stable_identifier}; reproduce and freeze an "
                            "implementation before module integration"
                        )
                        if baseline_inferred and baseline_evidence is not None
                        else (
                            f"published source {baseline_evidence.stable_identifier}; "
                            "implementation commit unresolved"
                        )
                    )
                )
            )
        ),
        source_evidence_id=baseline_source_evidence_id,
        license=(
            _metadata_text(baseline_evidence.metadata, "license")
            if baseline_evidence is not None
            else None
        ),
''',
        "baseline source-specific metadata",
    )
    replace_once(
        METHOD,
        '''        evidence_id=primary.evidence_id,
        original_role=draft.module_original_role,
        proposed_role=draft.module_proposed_role,
        license=_metadata_text(primary.metadata, "license"),
''',
        '''        evidence_id=module_primary.evidence_id,
        original_role=draft.module_original_role,
        proposed_role=draft.module_proposed_role,
        license=_metadata_text(module_primary.metadata, "license"),
''',
        "module source evidence",
    )
    replace_once(
        METHOD,
        '''            source_evidence_id=primary.evidence_id,
            comparator=baseline_name,
            purpose="isolate the causal contribution of the proposed module",
''',
        '''            source_evidence_id=module_primary.evidence_id,
            comparator=baseline_name,
            purpose="isolate the causal contribution of the proposed module",
''',
        "single module source",
    )
    replace_once(
        METHOD,
        '''            source_evidence_id=primary.evidence_id,
            comparator=baseline_name,
            purpose="measure the complete minimal method under the same evaluation contract",
''',
        '''            source_evidence_id=module_primary.evidence_id,
            comparator=baseline_name,
            purpose="measure the complete minimal method under the same evaluation contract",
''',
        "full method source",
    )
    replace_once(
        METHOD,
        '''            "baseline reproduction and disabled-module parity are not yet verified",
''',
        '''            (
                "baseline identity is unresolved; retrieve and reproduce an evidence-bound "
                "task-matched comparator before claiming a baseline result"
                if baseline_unresolved
                else "baseline reproduction and disabled-module parity are not yet verified"
            ),
''',
        "unresolved baseline risk",
    )


def patch_tests() -> None:
    append_once(
        ADAPTER_TEST,
        "test_direct_query_paper_is_not_a_baseline_candidate",
        '''


def test_direct_query_paper_is_not_a_baseline_candidate() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-direct",
        gap_id="g-direct",
        query="few-shot industrial anomaly method",
        source_types=["paper"],
    )
    candidate = adapter._candidate(query, _paper("A Relevant Neighbor Method"), False)
    assert candidate.metadata["relation"] == "direct_query"
    assert "baseline_candidate" not in candidate.metadata


def test_dataset_parallel_paper_is_an_inferred_baseline_candidate() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-parallel",
        gap_id="g-parallel",
        query="MIMII dataset baseline comparison",
        source_types=["paper", "dataset"],
    )
    candidate = adapter._candidate(
        query,
        _paper("A Task-Matched MIMII Comparator"),
        False,
        relation="parallel_via_dataset",
    )
    assert candidate.metadata["baseline_candidate"] == "inferred"


def test_declared_identity_remains_a_declared_baseline_candidate() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-declared",
        gap_id="g-declared",
        query='"Exact Baseline Paper"',
        source_types=["paper"],
    )
    candidate = adapter._candidate(
        query,
        _paper("Exact Baseline Paper"),
        False,
        relation="declared_identity",
    )
    assert candidate.metadata["baseline_candidate"] == "declared"
''',
    )
    replace_once(
        ANCHOR_TEST,
        '''    _select_dataset_evidence,
    _select_declared_baseline_evidence,
    _select_primary_evidence,
''',
        '''    _select_dataset_evidence,
    _select_declared_baseline_evidence,
    _select_inferred_baseline_evidence,
    _select_module_evidence,
    _select_primary_evidence,
''',
        "anchor test imports",
    )
    append_once(
        ANCHOR_TEST,
        "test_direct_query_neighbor_is_module_evidence_not_baseline",
        '''


def test_direct_query_neighbor_is_module_evidence_not_baseline() -> None:
    direct = _item(
        "direct-only",
        "A Relevant Mechanism Paper",
        metadata={
            "relation": "direct_query",
            "rank_score": "0.95",
        },
    )
    assert _select_inferred_baseline_evidence((direct,)) is None
    module = _select_module_evidence((direct,), baseline=None)
    assert module is not None
    assert module.evidence_id == "direct-only"


def test_direct_query_cannot_self_declare_inferred_baseline() -> None:
    direct = _item(
        "direct-marker",
        "A Direct Query Paper",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "direct_query",
            "rank_score": "0.99",
        },
    )
    assert _select_inferred_baseline_evidence((direct,)) is None
''',
    )
    replace_once(
        METHOD_TEST,
        '''        metadata={
            "doi": "10.3390/s24175496",
            "candidate_gap_ids": "baseline_comparison,failure_mechanism",
            "license": "CC BY 4.0",
        },
''',
        '''        metadata={
            "doi": "10.3390/s24175496",
            "candidate_gap_ids": "baseline_comparison,failure_mechanism",
            "license": "CC BY 4.0",
            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.90",
        },
''',
        "method fixture inferred baseline marker",
    )
    append_once(
        METHOD_TEST,
        "test_unqualified_direct_paper_does_not_become_baseline",
        '''


def test_unqualified_direct_paper_does_not_become_baseline() -> None:
    state = _state()
    evidence = state["evidence"]
    assert evidence is not None
    direct_item = evidence.items[0].model_copy(
        update={
            "metadata": {
                "doi": "10.3390/s24175496",
                "relation": "direct_query",
                "rank_score": "0.99",
                "license": "CC BY 4.0",
            }
        }
    )
    direct_state = cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(update={"items": [direct_item]}),
        },
    )
    proposal = build_method_proposal(
        direct_state,
        _draft(
            baseline_readiness_confirmed=True,
            evaluation_protocol_validated=True,
            module_validation_confirmed=True,
        ),
    )
    plan = proposal.methodology_plan
    assert plan.baseline.source_evidence_id is None
    assert plan.baseline.reproduced is False
    assert plan.baseline.baseline_parity_verified is False
    assert "unresolved task-matched baseline" in plan.baseline.name
    assert plan.research.baseline_readiness_confirmed is False
    assert plan.modules[0].evidence_id == _EVIDENCE_ID
    experiments = {experiment.name: experiment for experiment in plan.experiments}
    assert experiments["E0-frozen-baseline"].source_evidence_id is None
    assert experiments["E1-single-module"].source_evidence_id == _EVIDENCE_ID
    assert experiments["E2-full-method"].source_evidence_id == _EVIDENCE_ID
''',
    )


def main() -> int:
    patch_adapter()
    patch_method()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
