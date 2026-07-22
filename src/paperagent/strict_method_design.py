from __future__ import annotations

import re
from collections.abc import Iterable

from paperagent.method_design_draft import (
    MethodDesignDraft,
    _titles_equivalent,
    build_method_proposal,
)
from paperagent.schemas.evidence import EvidenceBundle, EvidenceItem
from paperagent.schemas.method import MethodProposal
from paperagent.state import PaperAgentState

_DECLARED_ROLE_SUFFIX = re.compile(
    r"\s*\[declared role:(?P<role>[^\]]+)\]\s*$",
    re.IGNORECASE,
)


def _declared_titles(references: Iterable[str], *, role_tokens: tuple[str, ...]) -> tuple[str, ...]:
    titles: list[str] = []
    for reference in references:
        match = _DECLARED_ROLE_SUFFIX.search(reference)
        if match is None:
            continue
        role = match.group("role").casefold()
        if not any(token in role for token in role_tokens):
            continue
        title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)


def _declared_baseline_titles(references: Iterable[str]) -> tuple[str, ...]:
    return _declared_titles(references, role_tokens=("baseline",))


def _declared_module_titles(references: Iterable[str]) -> tuple[str, ...]:
    titles: list[str] = []
    for reference in references:
        match = _DECLARED_ROLE_SUFFIX.search(reference)
        if match is None:
            continue
        role = match.group("role").casefold()
        if "baseline" in role or not any(token in role for token in ("module", "parallel")):
            continue
        title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)


def _accepted_papers(evidence: EvidenceBundle) -> tuple[EvidenceItem, ...]:
    accepted_ids = set(evidence.accepted_ids)
    return tuple(
        item
        for item in evidence.items
        if item.evidence_id in accepted_ids and item.source_type == "paper"
    )


def _find_title(
    papers: tuple[EvidenceItem, ...],
    titles: tuple[str, ...],
) -> EvidenceItem | None:
    for title in titles:
        for item in papers:
            if _titles_equivalent(item.title, title):
                return item
    return None


def _prepare_role_bound_state(state: PaperAgentState) -> PaperAgentState:
    request = state.get("request")
    evidence = state.get("evidence")
    if request is None or evidence is None:
        raise ValueError("request and evidence are required for strict method canonicalization")

    references = tuple(request.user_material_refs)
    baseline_titles = _declared_baseline_titles(references)
    module_titles = _declared_module_titles(references)
    papers = _accepted_papers(evidence)

    declared_baseline = _find_title(papers, baseline_titles)
    if baseline_titles and declared_baseline is None:
        raise ValueError(
            "declared baseline identity unresolved in accepted evidence; "
            "do not substitute an inferred or repository-backed baseline"
        )

    declared_module = _find_title(papers, module_titles)
    if module_titles and declared_module is None:
        raise ValueError(
            "declared parallel/module source unresolved in accepted evidence; "
            "do not synthesize an unattributed replacement module"
        )

    if declared_baseline is not None and declared_module is not None:
        if declared_baseline.evidence_id == declared_module.evidence_id:
            raise ValueError(
                "baseline and declared module source must be independent evidence items"
            )

    if declared_module is None:
        return state

    # The legacy canonicalizer ranks direct-query papers above declared-identity papers
    # when selecting module evidence. Re-rank only the accepted declared module in a
    # state-local copy so server-owned selection cannot drift to an unrelated paper.
    patched_items: list[EvidenceItem] = []
    for item in evidence.items:
        if item.evidence_id != declared_module.evidence_id:
            patched_items.append(item)
            continue
        metadata = dict(item.metadata)
        metadata.pop("baseline_candidate", None)
        metadata.pop("comparator_candidate", None)
        metadata["relation"] = "direct_query"
        metadata["rank_score"] = "1000000"
        metadata["role_binding"] = "declared_parallel_method"
        patched_items.append(item.model_copy(update={"metadata": metadata}))

    patched_evidence = evidence.model_copy(update={"items": patched_items})
    patched_state = dict(state)
    patched_state["evidence"] = patched_evidence
    return patched_state  # type: ignore[return-value]


def _proposal_evidence_title(proposal: MethodProposal, evidence_id: str | None) -> str | None:
    if evidence_id is None:
        return None
    for item in proposal.methodology_plan.evidence:
        if item.evidence_id == evidence_id:
            return item.title
    return None


def _validate_role_bindings(state: PaperAgentState, proposal: MethodProposal) -> None:
    request = state.get("request")
    if request is None:
        raise ValueError("request is required for role-binding validation")
    references = tuple(request.user_material_refs)
    baseline_titles = _declared_baseline_titles(references)
    module_titles = _declared_module_titles(references)

    baseline = proposal.methodology_plan.baseline
    baseline_title = _proposal_evidence_title(proposal, baseline.source_evidence_id)
    if baseline_titles and (
        baseline_title is None
        or not any(_titles_equivalent(baseline_title, title) for title in baseline_titles)
    ):
        raise ValueError("canonical proposal baseline is not bound to the declared baseline paper")

    if module_titles:
        if not proposal.methodology_plan.modules:
            raise ValueError("canonical proposal omitted the declared module source")
        for module in proposal.methodology_plan.modules:
            module_title = _proposal_evidence_title(proposal, module.evidence_id)
            if module_title is None or not any(
                _titles_equivalent(module_title, title) for title in module_titles
            ):
                raise ValueError(
                    "canonical proposal module is not bound to the declared parallel/module paper"
                )
            if module.evidence_id == baseline.source_evidence_id:
                raise ValueError(
                    "baseline evidence cannot be reused as independent module evidence"
                )


def build_role_bound_method_proposal(
    state: PaperAgentState,
    draft: MethodDesignDraft,
) -> MethodProposal:
    """Canonicalize a method while enforcing user-declared evidence roles.

    This wrapper is deliberately generic: it only enforces identities and roles declared
    by the user. It contains no benchmark case IDs, domain tables, Gold decisions, or
    expected answers.
    """

    prepared_state = _prepare_role_bound_state(state)
    proposal = build_method_proposal(prepared_state, draft)
    _validate_role_bindings(state, proposal)
    return proposal


__all__ = ["build_role_bound_method_proposal"]
