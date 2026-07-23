from __future__ import annotations

from pathlib import Path

LITERATURE_ADAPTER = Path("src/paperagent/literature/adapter.py")
PLANNING = Path("src/paperagent/nodes/planning.py")
METHOD_DESIGN = Path("src/paperagent/method_design_draft.py")


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def prepatch_literature() -> None:
    replace_exact(
        LITERATURE_ADAPTER,
        '''        for paper in selected:
            relation = (
                "declared_identity"
                if required_title is not None
                and _exact_title_match(paper.canonical_title, required_title)
                else (
                    "parallel_via_dataset"
                    if paper.paper_id in relation_paper_ids
                    else (
                        "baseline_role_query"
                        if _query_candidate_role(query.query) == "baseline"
                        else (
                            "comparator_role_query"
                            if _query_candidate_role(query.query) == "comparator"
                            else "direct_query"
                        )
                    )
                )
            )
''',
        '''        query_role = _query_candidate_role(query.query)
        for paper in selected:
            exact_declared_identity = required_title is not None and _exact_title_match(
                paper.canonical_title, required_title
            )
            relation = (
                "module_role_query"
                if exact_declared_identity and query_role == "module"
                else (
                    "declared_identity"
                    if exact_declared_identity
                    else (
                        "module_linked_by_focused_retrieval"
                        if paper.paper_id in relation_paper_ids and query_role == "module"
                        else (
                            "parallel_via_dataset"
                            if paper.paper_id in relation_paper_ids
                            else (
                                "baseline_role_query"
                                if query_role == "baseline"
                                else (
                                    "comparator_role_query"
                                    if query_role == "comparator"
                                    else (
                                        "module_role_query"
                                        if query_role == "module"
                                        else "direct_query"
                                    )
                                )
                            )
                        )
                    )
                )
            )
''',
        "literature relation",
    )
    replace_exact(
        LITERATURE_ADAPTER,
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
        '''                **(
                    {"baseline_candidate": "declared"}
                    if relation == "declared_identity"
                    else (
                        {"baseline_candidate": "inferred"}
                        if relation in {"parallel_via_dataset", "baseline_role_query"}
                        else (
                            {"comparator_candidate": "inferred"}
                            if relation == "comparator_role_query"
                            else (
                                {"module_candidate": "inferred"}
                                if relation
                                in {
                                    "module_role_query",
                                    "parallel_method_query",
                                    "module_linked_by_focused_retrieval",
                                }
                                else {}
                            )
                        )
                    )
                ),
''',
        "literature module metadata",
    )


def prepatch_planning_queries() -> None:
    replace_exact(
        PLANNING,
        '''        exact_title = identity.title.replace('"', " ").strip()
        identity_gaps.append(
''',
        '''        exact_title = identity.title.replace('"', " ").strip()
        role_hint = _material_query_role_hint(identity.reference)
        identity_gaps.append(
''',
        "planning material role hint",
    )
    replace_exact(
        PLANNING,
        '''                query=f'"{exact_title}"',
''',
        '''                query=f'"{exact_title}"{role_hint}',
''',
        "planning exact-title role query",
    )
    replace_exact(
        PLANNING,
        '''                query=f'"{exact_title}" official implementation code repository',
''',
        '''                query=(
                    f'"{exact_title}" official implementation code repository'
                    f'{_material_query_role_hint(identity.reference)}'
                ),
''',
        "planning repository role query",
    )


def prepatch_method_design() -> None:
    replace_exact(
        METHOD_DESIGN,
        "from paperagent.scientific_readiness import derive_scientific_readiness\n",
        "from paperagent.module_compatibility import (\n"
        "    MODULE_EVIDENCE_RELATIONS,\n"
        "    evaluate_module_compatibility,\n"
        ")\n"
        "from paperagent.scientific_readiness import derive_scientific_readiness\n",
        "method design compatibility import",
    )
    replace_exact(
        METHOD_DESIGN,
        '''    input_semantics: str = Field(min_length=5)
    output_semantics: str = Field(min_length=5)
    predicted_effect: str = Field(min_length=5)
''',
        '''    input_semantics: str = Field(min_length=5)
    output_semantics: str = Field(min_length=5)
    input_shape: str = Field(min_length=3)
    output_shape: str = Field(min_length=3)
    insertion_point: str = Field(min_length=5)
    normalization_contract: str = Field(min_length=5)
    masking_contract: str = Field(min_length=5)
    gradient_path: str = Field(min_length=5)
    trainable_parameters: str = Field(min_length=5)
    frozen_parameters: str = Field(min_length=5)
    loss_terms: list[str] = Field(min_length=1, max_length=8)
    loss_weighting: str = Field(min_length=5)
    predicted_effect: str = Field(min_length=5)
''',
        "method design structured fields",
    )
    baseline_titles = '''def _declared_baseline_titles(references: list[str]) -> tuple[str, ...]:
    titles: list[str] = []
    for reference in references:
        match = _DECLARED_ROLE_SUFFIX.search(reference)
        if match is None or "baseline" not in match.group("role").casefold():
            continue
        title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)
'''
    module_titles = '''


def _declared_module_titles(references: list[str]) -> tuple[str, ...]:
    titles: list[str] = []
    for reference in references:
        match = _DECLARED_ROLE_SUFFIX.search(reference)
        if match is None:
            continue
        role = match.group("role").casefold()
        if not any(token in role for token in ("parallel", "module", "mechanism")):
            continue
        title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)
'''
    text = METHOD_DESIGN.read_text(encoding="utf-8")
    if "def _declared_module_titles" not in text:
        if text.count(baseline_titles) != 1:
            raise RuntimeError("declared baseline title helper shape changed")
        METHOD_DESIGN.write_text(
            text.replace(baseline_titles, baseline_titles + module_titles),
            encoding="utf-8",
        )

    replace_exact(
        METHOD_DESIGN,
        '''def _module_evidence_rank(
    item: EvidenceItem,
    *,
    baseline_evidence_id: str | None,
) -> tuple[int, int, float, str]:
    if item.source_type != "paper":
        return (-1, -1, -1.0, item.evidence_id)
    relation = item.metadata.get("relation", "")
    relation_rank = {
        "direct_query": 4,
        "baseline_role_query": 3,
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
    papers = tuple(
        item
        for item in candidates
        if item.source_type == "paper"
        and item.metadata.get("comparator_candidate") != "inferred"
        and item.metadata.get("relation") != "comparator_role_query"
    )
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
        '''def _module_evidence_rank(item: EvidenceItem) -> tuple[int, float, float, str]:
    relation_rank = {
        "module_role_query": 3,
        "parallel_method_query": 2,
        "module_linked_by_focused_retrieval": 1,
    }.get(item.metadata.get("relation", ""), 0)
    try:
        relevance = float(item.metadata.get("relevance_score", "0"))
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        relevance = 0.0
        rank_score = 0.0
    return (relation_rank, relevance, rank_score, item.evidence_id)


def _module_candidate_marker(item: EvidenceItem) -> bool:
    return item.metadata.get("module_candidate", "").casefold() in {
        "true",
        "1",
        "yes",
        "declared",
        "inferred",
    }


def _select_module_evidence(
    candidates: tuple[EvidenceItem, ...],
    *,
    baseline: EvidenceItem | None,
    declared_titles: tuple[str, ...],
) -> EvidenceItem | None:
    baseline_id = baseline.evidence_id if baseline is not None else None
    papers: list[EvidenceItem] = []
    for item in candidates:
        if (
            item.source_type != "paper"
            or item.evidence_id == baseline_id
            or item.metadata.get("relation") not in MODULE_EVIDENCE_RELATIONS
            or not _module_candidate_marker(item)
            or item.metadata.get("comparator_candidate") == "inferred"
            or _is_review_evidence(item.title, item.summary)
        ):
            continue
        try:
            relevance = float(item.metadata.get("relevance_score", "0"))
            rank_score = float(item.metadata.get("rank_score", "0"))
        except ValueError:
            continue
        if relevance < 0.25 or rank_score < 0.50:
            continue
        if declared_titles and not any(
            _titles_equivalent(item.title, title) for title in declared_titles
        ):
            continue
        papers.append(item)
    if not papers:
        return None
    return max(papers, key=_module_evidence_rank)
''',
        "module evidence selection",
    )
    replace_exact(
        METHOD_DESIGN,
        '''    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    ) or _select_inferred_baseline_evidence(method_evidence)
    if baseline_evidence is None:
        baseline_evidence = _select_repository_backed_direct_baseline(method_evidence)
    module_primary = _select_module_evidence(method_evidence, baseline=baseline_evidence)
    if module_primary is None:
        raise ValueError("method canonicalization requires accepted paper evidence")
''',
        '''    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    declared_module_titles = _declared_module_titles(list(request.user_material_refs))
    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    ) or _select_inferred_baseline_evidence(method_evidence)
    if baseline_evidence is None:
        baseline_evidence = _select_repository_backed_direct_baseline(method_evidence)
    module_primary = _select_module_evidence(
        method_evidence,
        baseline=baseline_evidence,
        declared_titles=declared_module_titles,
    )
    if module_primary is None:
        raise ValueError(
            "module_design_deferred: independent accepted module-lane evidence is unavailable"
        )
''',
        "module evidence binding",
    )
    replace_exact(
        METHOD_DESIGN,
        '''    module = ModuleCard(
        name=module_name,
        evidence_id=module_primary.evidence_id,
        original_role=draft.module_original_role,
        proposed_role=draft.module_proposed_role,
        license=_metadata_text(module_primary.metadata, "license"),
        input_semantics=draft.input_semantics,
        output_semantics=draft.output_semantics,
        input_shape=(
            "task-specific representation at the selected insertion point; exact dimensions "
            "are resolved after the baseline is frozen"
        ),
        output_shape="representation contract required by the downstream baseline stage",
        normalization="inherit and freeze the baseline normalization contract",
        masks=(
            "inherit baseline target and padding masks; introduce no new mask semantics initially"
        ),
        ordering="insert one independently switchable module at the selected representation stage",
        trainable=True,
        loss_terms=("inherit baseline task losses and weights for the first pilot",),
        gradient_expectation=(
            "verify non-zero finite gradients in the module and connected baseline path"
        ),
        parameter_update_scope=(
            "train the candidate module and matched baseline parameters under the same budget"
        ),
        loss_scale=(
            "keep baseline loss scaling unchanged unless a documented pilot failure requires repair"
        ),
        compute_cost=draft.compute_cost,
        assumptions=_dedupe(
            (*plan_risks, "the selected insertion point preserves representation semantics")
        ),
        predicted_effect=draft.predicted_effect,
        failure_mode=draft.failure_mode,
        implementation_switch=module_switch,
        baseline_parity_behavior=(
            "when disabled, the module contributes no parameters, operations, "
            "preprocessing, or loss terms"
        ),
    )
''',
        '''    module = ModuleCard(
        name=module_name,
        evidence_id=module_primary.evidence_id,
        original_role=draft.module_original_role,
        proposed_role=draft.module_proposed_role,
        license=_metadata_text(module_primary.metadata, "license"),
        input_semantics=draft.input_semantics,
        output_semantics=draft.output_semantics,
        input_shape=draft.input_shape,
        output_shape=draft.output_shape,
        insertion_point=draft.insertion_point,
        normalization_contract=draft.normalization_contract,
        masking_contract=draft.masking_contract,
        gradient_path=draft.gradient_path,
        trainable_parameters=draft.trainable_parameters,
        frozen_parameters=draft.frozen_parameters,
        loss_weighting=draft.loss_weighting,
        normalization=draft.normalization_contract,
        masks=draft.masking_contract,
        ordering=draft.insertion_point,
        trainable=True,
        loss_terms=tuple(draft.loss_terms),
        gradient_expectation=draft.gradient_path,
        parameter_update_scope=(
            f"trainable: {draft.trainable_parameters}; frozen: {draft.frozen_parameters}"
        ),
        loss_scale=draft.loss_weighting,
        compute_cost=draft.compute_cost,
        assumptions=plan_risks,
        predicted_effect=draft.predicted_effect,
        failure_mode=draft.failure_mode,
        implementation_switch=module_switch,
        baseline_parity_behavior=(
            "when disabled, remove this module's operations, parameters, and auxiliary losses "
            "while preserving the frozen baseline path byte-for-byte"
        ),
    )
    compatibility = evaluate_module_compatibility(
        module=module,
        evidence=module_primary,
        accepted_ids=evidence_bundle.accepted_ids,
        baseline_evidence_id=baseline_source_evidence_id,
        target_text=" ".join(
            (
                request.question,
                plan.problem_statement,
                plan.scope,
                draft.module_proposed_role,
            )
        ),
    )
    if not compatibility.compatible:
        raise ValueError("module_design_deferred: " + ",".join(compatibility.reasons))
''',
        "module card construction",
    )
    replace_exact(
        METHOD_DESIGN,
        '                from_module="frozen_baseline_representation_stage",\n',
        "                from_module=draft.insertion_point,\n",
        "integration insertion point",
    )


def apply_all() -> None:
    prepatch_literature()
    prepatch_planning_queries()
    prepatch_method_design()


if __name__ == "__main__":
    apply_all()
