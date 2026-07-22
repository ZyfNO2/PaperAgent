from __future__ import annotations

from pathlib import Path

METHOD = Path("src/paperagent/method_design_draft.py")
STRICT = Path("src/paperagent/strict_method_design.py")
TEST = Path("tests/methodology/test_strict_method_design.py")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, found {count}: {old[:120]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    method = METHOD.read_text(encoding="utf-8")
    method = replace_once(
        method,
        '''    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)



def _comparator_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
''',
        '''    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)



def _select_baseline_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    """Resolve a baseline without letting an inferred paper override a declaration.

    A declared title match has first priority. If that identity is absent from accepted
    evidence, a verified direct-query paper with an accepted author-linked repository is
    allowed as the evidence-bound fallback. Inferred baseline-role candidates are used only
    when the user did not declare a baseline identity.
    """

    if _declared_baseline_titles(references):
        return _select_declared_baseline_evidence(
            references, candidates
        ) or _select_repository_backed_direct_baseline(candidates)
    return _select_inferred_baseline_evidence(
        candidates
    ) or _select_repository_backed_direct_baseline(candidates)



def _comparator_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
''',
    )
    method = replace_once(
        method,
        '''    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    ) or _select_inferred_baseline_evidence(method_evidence)
    if baseline_evidence is None:
        baseline_evidence = _select_repository_backed_direct_baseline(method_evidence)
''',
        '''    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    baseline_evidence = _select_baseline_evidence(
        list(request.user_material_refs), method_evidence
    )
''',
    )
    METHOD.write_text(method, encoding="utf-8")

    strict = STRICT.read_text(encoding="utf-8")
    strict = replace_once(
        strict,
        '''from paperagent.method_design_draft import (
    MethodDesignDraft,
    _titles_equivalent,
    build_method_proposal,
)
''',
        '''from paperagent.method_design_draft import (
    MethodDesignDraft,
    _select_baseline_evidence,
    _titles_equivalent,
    build_method_proposal,
)
''',
    )
    strict = replace_once(
        strict,
        '''def _accepted_papers(evidence: EvidenceBundle) -> tuple[EvidenceItem, ...]:
    accepted_ids = set(evidence.accepted_ids)
    return tuple(
        item
        for item in evidence.items
        if item.evidence_id in accepted_ids and item.source_type == "paper"
    )
''',
        '''def _accepted_items(evidence: EvidenceBundle) -> tuple[EvidenceItem, ...]:
    accepted_ids = set(evidence.accepted_ids)
    return tuple(item for item in evidence.items if item.evidence_id in accepted_ids)



def _accepted_papers(evidence: EvidenceBundle) -> tuple[EvidenceItem, ...]:
    return tuple(item for item in _accepted_items(evidence) if item.source_type == "paper")
''',
    )
    strict = replace_once(
        strict,
        '''    papers = _accepted_papers(evidence)

    declared_baseline = _find_title(papers, baseline_titles)
    if baseline_titles and declared_baseline is None:
        raise ValueError(
            "declared baseline identity unresolved in accepted evidence; "
            "do not substitute an inferred or repository-backed baseline"
        )
''',
        '''    accepted = _accepted_items(evidence)
    papers = tuple(item for item in accepted if item.source_type == "paper")

    declared_baseline = _find_title(papers, baseline_titles)
    selected_baseline = _select_baseline_evidence(list(references), accepted)
    if baseline_titles and declared_baseline is None and selected_baseline is None:
        raise ValueError(
            "declared baseline identity unresolved in accepted evidence and no "
            "repository-backed direct fallback is available"
        )
''',
    )
    strict = replace_once(
        strict,
        '''    if (
        declared_baseline is not None
        and declared_module is not None
        and declared_baseline.evidence_id == declared_module.evidence_id
    ):
''',
        '''    if (
        selected_baseline is not None
        and declared_module is not None
        and selected_baseline.evidence_id == declared_module.evidence_id
    ):
''',
    )
    strict = replace_once(
        strict,
        '''def _validate_role_bindings(state: PaperAgentState, proposal: MethodProposal) -> None:
    request = state.get("request")
    if request is None:
        raise ValueError("request is required for role-binding validation")
''',
        '''def _validate_role_bindings(state: PaperAgentState, proposal: MethodProposal) -> None:
    request = state.get("request")
    evidence = state.get("evidence")
    if request is None or evidence is None:
        raise ValueError("request and evidence are required for role-binding validation")
''',
    )
    strict = replace_once(
        strict,
        '''    baseline = proposal.methodology_plan.baseline
    baseline_title = _proposal_evidence_title(proposal, baseline.source_evidence_id)
    if baseline_titles and (
        baseline_title is None
        or not any(_titles_equivalent(baseline_title, title) for title in baseline_titles)
    ):
        raise ValueError("canonical proposal baseline is not bound to the declared baseline paper")
''',
        '''    baseline = proposal.methodology_plan.baseline
    baseline_title = _proposal_evidence_title(proposal, baseline.source_evidence_id)
    exact_declared_baseline = baseline_title is not None and any(
        _titles_equivalent(baseline_title, title) for title in baseline_titles
    )
    selected_baseline = _select_baseline_evidence(
        list(references), _accepted_items(evidence)
    )
    fallback_bound = (
        selected_baseline is not None
        and baseline.source_evidence_id == selected_baseline.evidence_id
    )
    if baseline_titles and not exact_declared_baseline and not fallback_bound:
        raise ValueError(
            "canonical proposal baseline is neither the declared baseline nor the "
            "repository-backed direct fallback"
        )
''',
    )
    STRICT.write_text(strict, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    test = replace_once(
        test,
        '''from paperagent.schemas import EvidenceBundle, EvidenceItem, ResearchRequest
from paperagent.strict_method_design import _prepare_role_bound_state
''',
        '''from paperagent.method_design_draft import _select_baseline_evidence
from paperagent.schemas import EvidenceBundle, EvidenceItem, ResearchRequest
from paperagent.strict_method_design import _prepare_role_bound_state
''',
    )
    test = replace_once(
        test,
        '''def _state(
''',
        '''def _repository(evidence_id: str, *, parent_paper_id: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="repository",
        title=f"Repository for {parent_paper_id}",
        locator=f"https://github.com/example/{parent_paper_id}",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary="Accepted author-linked implementation repository.",
        content_hash=f"sha256:{evidence_id}",
        metadata={
            "relation": "author_linked_from_verified_paper",
            "parent_paper_id": parent_paper_id,
        },
    )



def _state(
''',
    )
    test = replace_once(
        test,
        '''def test_declared_bert_does_not_match_beit_visual_transformer() -> None:
''',
        '''def test_declared_baseline_miss_uses_repository_backed_direct_fallback() -> None:
    declared = "USAD: UnSupervised Anomaly Detection on Multivariate Time Series"
    fallback = _paper(
        "ev-repository-baseline",
        "A Repository-Backed Direct Anomaly Detection Baseline",
        relation="direct_query",
    )
    repository = _repository("repo-baseline", parent_paper_id="repository-baseline")
    references = [f"{declared} [declared role:baseline]"]
    state = _state(references, [fallback, repository])

    prepared = _prepare_role_bound_state(state)  # type: ignore[arg-type]
    selected = _select_baseline_evidence(
        references,
        tuple(prepared["evidence"].accepted_items()),
    )

    assert selected is not None
    assert selected.evidence_id == fallback.evidence_id



def test_declared_bert_does_not_match_beit_visual_transformer() -> None:
''',
    )
    TEST.write_text(test, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
