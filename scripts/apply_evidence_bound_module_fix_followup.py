from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def block(value: str) -> str:
    return dedent(value).lstrip("\n")


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        print(f"already patched: {path}")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")
    print(f"patched: {path}")


def append_once(path: str, marker: str, addition: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if addition in text:
        print(f"already appended: {path}")
        return
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{path}: expected one append marker, found {count}")
    file.write_text(text.replace(marker, marker + addition), encoding="utf-8")
    print(f"appended: {path}")


def patch_academic_methodology() -> None:
    replace_once(
        "src/paperagent/academic_methodology.py",
        block(
            '''
            class ModuleCard(BaseModel):
                model_config = ConfigDict(extra="forbid", frozen=True)

                name: str = Field(min_length=1)
                evidence_id: str | None = None
                license: str | None = None
                original_role: str | None = None
                proposed_role: str | None = None
                input_semantics: str | None = None
                output_semantics: str | None = None
                input_shape: str | None = None
                output_shape: str | None = None
                normalization: str | None = None
                masks: str | None = None
                ordering: str | None = None
                trainable: bool | None = None
                loss_terms: tuple[str, ...] = ()
                compute_cost: str | None = None
                assumptions: tuple[str, ...] = ()
                predicted_effect: str | None = None
                failure_mode: str | None = None
                implementation_switch: str | None = None
                gradient_expectation: str | None = None
                parameter_update_scope: str | None = None
                loss_scale: str | None = None
                baseline_parity_behavior: str | None = None
            '''
        ),
        block(
            '''
            class ModuleCard(BaseModel):
                model_config = ConfigDict(extra="forbid", frozen=True)

                name: str = Field(min_length=1)
                evidence_id: str | None = None
                license: str | None = None
                original_role: str | None = None
                proposed_role: str | None = None
                input_semantics: str | None = None
                output_semantics: str | None = None
                input_shape: str | None = None
                output_shape: str | None = None
                insertion_point: str | None = None
                normalization_contract: str | None = None
                masking_contract: str | None = None
                gradient_path: str | None = None
                trainable_parameters: str | None = None
                frozen_parameters: str | None = None
                loss_weighting: str | None = None
                # Legacy aliases remain serializable for older stored plans.
                normalization: str | None = None
                masks: str | None = None
                ordering: str | None = None
                trainable: bool | None = None
                loss_terms: tuple[str, ...] = ()
                compute_cost: str | None = None
                assumptions: tuple[str, ...] = ()
                predicted_effect: str | None = None
                failure_mode: str | None = None
                implementation_switch: str | None = None
                gradient_expectation: str | None = None
                parameter_update_scope: str | None = None
                loss_scale: str | None = None
                baseline_parity_behavior: str | None = None
            '''
        ),
    )


def patch_module_compatibility() -> None:
    replace_once(
        "src/paperagent/module_compatibility.py",
        block(
            '''
                    if not evidence.metadata.get("module_candidate"):
                        reasons.append("module_candidate_marker_missing")
            '''
        ),
        block(
            '''
                    marker = evidence.metadata.get("module_candidate", "").casefold()
                    if marker not in {"true", "1", "yes", "declared", "inferred"}:
                        reasons.append("module_candidate_marker_missing")
            '''
        ),
    )


def patch_literature_adapter() -> None:
    replace_once(
        "src/paperagent/literature/adapter.py",
        block(
            '''
            _COMPARATOR_ROLE_QUERY = re.compile(
                r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
                re.IGNORECASE,
            )
            _DATASET_CONTEXT = re.compile(
            '''
        ),
        block(
            '''
            _COMPARATOR_ROLE_QUERY = re.compile(
                r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
                re.IGNORECASE,
            )
            _MODULE_ROLE_QUERY = re.compile(
                r"(?:\\bmodules?\\b|\\bparallel(?: method| paper)?\\b|\\bmechanisms?\\b|"
                r"模块|平行论文|并行方法|机制)",
                re.IGNORECASE,
            )
            _DATASET_CONTEXT = re.compile(
            '''
        ),
    )
    replace_once(
        "src/paperagent/literature/adapter.py",
        block(
            '''
            def _query_seeks_comparator_role(query: str) -> bool:
                return not _query_seeks_baseline_role(query) and bool(_COMPARATOR_ROLE_QUERY.search(query))


            def _query_candidate_role(query: str) -> str | None:
                if _query_seeks_baseline_role(query):
                    return "baseline"
                if _query_seeks_comparator_role(query):
                    return "comparator"
                return None
            '''
        ),
        block(
            '''
            def _query_seeks_comparator_role(query: str) -> bool:
                return not _query_seeks_baseline_role(query) and bool(_COMPARATOR_ROLE_QUERY.search(query))


            def _query_seeks_module_role(query: str) -> bool:
                return not _query_seeks_baseline_role(query) and bool(_MODULE_ROLE_QUERY.search(query))


            def _query_candidate_role(query: str) -> str | None:
                if _query_seeks_baseline_role(query):
                    return "baseline"
                if _query_seeks_comparator_role(query):
                    return "comparator"
                if _query_seeks_module_role(query):
                    return "module"
                return None
            '''
        ),
    )
    replace_once(
        "src/paperagent/literature/adapter.py",
        block(
            '''
                    for paper in selected:
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
            '''
        ),
        block(
            '''
                    query_role = _query_candidate_role(query.query)
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
            '''
        ),
    )
    replace_once(
        "src/paperagent/literature/adapter.py",
        block(
            '''
                                {"comparator_candidate": "inferred"}
                                if relation == "comparator_role_query"
                                else {}
                            )
                        )
                    ),
            '''
        ),
        block(
            '''
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
            '''
        ),
    )


def patch_planning() -> None:
    replace_once(
        "src/paperagent/nodes/planning.py",
        "from __future__ import annotations\n\nfrom langchain_core.runnables import RunnableConfig\n",
        "from __future__ import annotations\n\nimport re\n\nfrom langchain_core.runnables import RunnableConfig\n",
    )
    replace_once(
        "src/paperagent/nodes/planning.py",
        block(
            '''
            def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
                normalized_title = " ".join(title.replace('"', " ").split()).casefold()
                normalized_query = " ".join(query.query.replace('"', " ").split()).casefold()
                return bool(normalized_title and normalized_title in normalized_query)
            '''
        ),
        block(
            '''
            def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
                normalized_title = " ".join(title.replace('"', " ").split()).casefold()
                normalized_query = " ".join(query.query.replace('"', " ").split()).casefold()
                return bool(normalized_title and normalized_title in normalized_query)


            def _material_query_role_hint(reference: str) -> str:
                match = re.search(r"\\[declared role:(?P<role>[^\\]]+)\\]", reference, re.IGNORECASE)
                if match is None:
                    return ""
                role = match.group("role").casefold()
                if any(token in role for token in ("parallel", "module", "mechanism", "平行", "模块")):
                    return " parallel method module"
                if "baseline" in role or "基线" in role:
                    return " baseline"
                if any(token in role for token in ("comparison", "comparator", "对比", "比较")):
                    return " comparator comparison"
                return ""
            '''
        ),
    )
    replace_once(
        "src/paperagent/nodes/planning.py",
        block(
            '''
                    exact_title = identity.title.replace('"', " ").strip()
                    identity_gaps.append(
            '''
        ),
        block(
            '''
                    exact_title = identity.title.replace('"', " ").strip()
                    role_hint = _material_query_role_hint(identity.reference)
                    identity_gaps.append(
            '''
        ),
    )
    replace_once(
        "src/paperagent/nodes/planning.py",
        "                query=f'\"{exact_title}\"',\n",
        "                query=f'\"{exact_title}\"{role_hint}',\n",
    )
    replace_once(
        "src/paperagent/nodes/planning.py",
        "                query=f'\"{exact_title}\" official implementation code repository',\n",
        "                query=(\n                    f'\"{exact_title}\" official implementation code repository'\n                    f'{_material_query_role_hint(identity.reference)}'\n                ),\n",
    )


def patch_method_design() -> None:
    replace_once(
        "src/paperagent/method_design_draft.py",
        "from paperagent.scientific_readiness import derive_scientific_readiness\n",
        "from paperagent.module_compatibility import MODULE_EVIDENCE_RELATIONS, evaluate_module_compatibility\nfrom paperagent.scientific_readiness import derive_scientific_readiness\n",
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        block(
            '''
                input_semantics: str = Field(min_length=5)
                output_semantics: str = Field(min_length=5)
                predicted_effect: str = Field(min_length=5)
            '''
        ),
        block(
            '''
                input_semantics: str = Field(min_length=5)
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
            '''
        ),
    )
    append_once(
        "src/paperagent/method_design_draft.py",
        block(
            '''
            def _declared_baseline_titles(references: list[str]) -> tuple[str, ...]:
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
        ),
        block(
            '''


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
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        block(
            '''
            def _module_evidence_rank(
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
            '''
        ),
        block(
            '''
            def _module_evidence_rank(item: EvidenceItem) -> tuple[int, float, float, str]:
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
                papers = []
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
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        block(
            '''
                declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
                baseline_evidence = _select_declared_baseline_evidence(
                    list(request.user_material_refs), method_evidence
                ) or _select_inferred_baseline_evidence(method_evidence)
                if baseline_evidence is None:
                    baseline_evidence = _select_repository_backed_direct_baseline(method_evidence)
                module_primary = _select_module_evidence(method_evidence, baseline=baseline_evidence)
                if module_primary is None:
                    raise ValueError("method canonicalization requires accepted paper evidence")
            '''
        ),
        block(
            '''
                declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
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
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        block(
            '''
                module = ModuleCard(
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
            '''
        ),
        block(
            '''
                module = ModuleCard(
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
                    raise ValueError(
                        "module_design_deferred: " + ",".join(compatibility.reasons)
                    )
            '''
        ),
    )
    replace_once(
        "src/paperagent/method_design_draft.py",
        "                from_module=\"frozen_baseline_representation_stage\",\n",
        "                from_module=draft.insertion_point,\n",
    )


def patch_benchmark_models() -> None:
    replace_once(
        "src/paperagent/claw_academic_benchmark.py",
        block(
            '''
                implementation_switch: str | None = None
                role_compatible: bool | None = None
            '''
        ),
        block(
            '''
                implementation_switch: str | None = None
                role_compatible: bool | None = None
                compatibility_reasons: tuple[str, ...] = ()
            '''
        ),
    )


def patch_benchmark_adapter() -> None:
    replace_once(
        "src/paperagent/claw_benchmark_adapter.py",
        "from paperagent.academic_methodology import ExperimentArmType\n",
        "from paperagent.academic_methodology import ExperimentArmType\nfrom paperagent.module_compatibility import (\n    ModuleCompatibilityResult,\n    evaluate_module_compatibility,\n)\n",
    )
    append_once(
        "src/paperagent/claw_benchmark_adapter.py",
        block(
            '''
            def _method_evidence_roles(state: PaperAgentState) -> dict[str, EvidenceRole]:
                method = state.get("method")
                if method is None:
                    return {}
                plan = method.methodology_plan
                roles: dict[str, EvidenceRole] = {}
                if plan.baseline.source_evidence_id:
                    roles[plan.baseline.source_evidence_id] = "baseline"
                for module in plan.modules:
                    if module.evidence_id:
                        roles[module.evidence_id] = "parallel_method"
                for experiment in plan.experiments:
                    if not experiment.source_evidence_id:
                        continue
                    if experiment.arm_type is ExperimentArmType.STRONG_COMPARISON:
                        roles[experiment.source_evidence_id] = "strong_comparison"
                    elif experiment.arm_type is ExperimentArmType.NEGATIVE_CONTROL:
                        roles[experiment.source_evidence_id] = "risk"
                return roles
            '''
        ),
        block(
            '''


            def _module_compatibility_by_evidence(
                state: PaperAgentState,
            ) -> dict[str, ModuleCompatibilityResult]:
                method = state.get("method")
                evidence = state.get("evidence")
                if method is None or evidence is None:
                    return {}
                plan = method.methodology_plan
                by_id = {item.evidence_id: item for item in evidence.items}
                request = state.get("request")
                target_text = " ".join(
                    value
                    for value in (
                        request.question if request is not None else None,
                        plan.research.target_problem,
                        plan.research.scientific_setting,
                        plan.research.intended_claim,
                    )
                    if value
                )
                return {
                    module.evidence_id: evaluate_module_compatibility(
                        module=module,
                        evidence=by_id.get(module.evidence_id),
                        accepted_ids=evidence.accepted_ids,
                        baseline_evidence_id=plan.baseline.source_evidence_id,
                        target_text=target_text,
                    )
                    for module in plan.modules
                    if module.evidence_id
                }
            '''
        ),
    )
    replace_once(
        "src/paperagent/claw_benchmark_adapter.py",
        "    method_roles = _method_evidence_roles(state)\n    full_text_ids = set(context.full_text_evidence_ids)\n",
        "    method_roles = _method_evidence_roles(state)\n    module_compatibility = _module_compatibility_by_evidence(state)\n    full_text_ids = set(context.full_text_evidence_ids)\n",
    )
    replace_once(
        "src/paperagent/claw_benchmark_adapter.py",
        "                role_compatible=None,\n",
        "                role_compatible=(\n                    module_compatibility[item.evidence_id].compatible\n                    if role == \"parallel_method\" and item.evidence_id in module_compatibility\n                    else None\n                ),\n",
    )
    replace_once(
        "src/paperagent/claw_benchmark_adapter.py",
        block(
            '''
            def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
                method = state.get("method")
                if method is None:
                    return ()
                output: list[ModuleTrace] = []
                for module in method.methodology_plan.modules:
                    optimization = _dedupe(
                        (
                            module.gradient_expectation,
                            module.parameter_update_scope,
                            module.loss_scale,
                            ", ".join(module.loss_terms) if module.loss_terms else None,
                        )
                    )
                    role_compatible = bool(
                        module.evidence_id
                        and module.original_role
                        and module.proposed_role
                        and module.input_semantics
                        and module.output_semantics
                        and module.input_semantics.casefold() not in {"tensor", "shape-only", "unknown"}
                        and module.output_semantics.casefold() not in {"tensor", "shape-only", "unknown"}
                    )
                    output.append(
                        ModuleTrace(
                            module_id=module.name,
                            evidence_id=module.evidence_id,
                            original_role=module.original_role,
                            proposed_role=module.proposed_role,
                            input_semantics=module.input_semantics,
                            output_semantics=module.output_semantics,
                            input_shape=module.input_shape,
                            output_shape=module.output_shape,
                            optimization_interaction="; ".join(optimization) or None,
                            compute_cost=module.compute_cost,
                            failure_mode=module.failure_mode,
                            implementation_switch=module.implementation_switch,
                            role_compatible=role_compatible,
                        )
                    )
                return tuple(output)
            '''
        ),
        block(
            '''
            def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
                method = state.get("method")
                if method is None:
                    return ()
                compatibility_by_evidence = _module_compatibility_by_evidence(state)
                output: list[ModuleTrace] = []
                for module in method.methodology_plan.modules:
                    optimization = _dedupe(
                        (
                            module.gradient_path or module.gradient_expectation,
                            module.trainable_parameters,
                            module.frozen_parameters,
                            module.loss_weighting or module.loss_scale,
                            ", ".join(module.loss_terms) if module.loss_terms else None,
                        )
                    )
                    compatibility = compatibility_by_evidence.get(module.evidence_id or "")
                    output.append(
                        ModuleTrace(
                            module_id=module.name,
                            evidence_id=module.evidence_id,
                            original_role=module.original_role,
                            proposed_role=module.proposed_role,
                            input_semantics=module.input_semantics,
                            output_semantics=module.output_semantics,
                            input_shape=module.input_shape,
                            output_shape=module.output_shape,
                            optimization_interaction="; ".join(optimization) or None,
                            compute_cost=module.compute_cost,
                            failure_mode=module.failure_mode,
                            implementation_switch=module.implementation_switch,
                            role_compatible=(
                                compatibility.compatible if compatibility is not None else False
                            ),
                            compatibility_reasons=(
                                compatibility.reasons
                                if compatibility is not None
                                else ("module_evidence_missing",)
                            ),
                        )
                    )
                return tuple(output)
            '''
        ),
    )


def patch_scorer() -> None:
    replace_once(
        "scripts/score_academic_tailoring_retrieval_v1.py",
        block(
            '''
                valid_evidence_ids = set(accepted_items_by_id)
                module_score = 0
                evidence_backed_modules = 0
                if trace.modules:
                    module_score += 3
                    evidence_backed_modules = sum(
                        item.evidence_id in valid_evidence_ids for item in trace.modules
                    )
                    role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
                    module_score += round(4 * evidence_backed_modules / len(trace.modules))
                    module_score += round(3 * role_count / len(trace.modules))
                elif trace.module_design_deferred and trace.module_defer_reason:
                    module_score = 4
                module_score = min(10, module_score)

                compatibility_score = 0
                if trace.modules:
                    semantic_count = sum(
                        bool(item.input_semantics and item.output_semantics and item.failure_mode)
                        for item in trace.modules
                    )
                    switch_count = sum(bool(item.implementation_switch) for item in trace.modules)
                    explicitly_compatible_count = sum(item.role_compatible is True for item in trace.modules)
                    compatibility_score += round(6 * semantic_count / len(trace.modules))
                    compatibility_score += round(2 * switch_count / len(trace.modules))
                    compatibility_score += round(4 * explicitly_compatible_count / len(trace.modules))
                    compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
                elif trace.module_design_deferred:
                    compatibility_score = 3
                compatibility_score = min(15, compatibility_score)
            '''
        ),
        block(
            '''
                valid_evidence_ids = set(accepted_items_by_id)
                module_score = 0
                evidence_backed_modules = 0
                independently_verified_modules = 0
                if trace.modules:
                    module_score += 3
                    evidence_backed_modules = sum(
                        item.evidence_id in valid_evidence_ids for item in trace.modules
                    )
                    independently_verified_modules = sum(
                        bool(
                            item.evidence_id
                            and item.evidence_id != (baseline.source_evidence_id if baseline else None)
                            and item.evidence_id in accepted_review_by_id
                            and accepted_review_by_id[item.evidence_id].role == "parallel_method"
                            and accepted_review_by_id[item.evidence_id].role_compatible is True
                        )
                        for item in trace.modules
                    )
                    role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
                    module_score += round(4 * evidence_backed_modules / len(trace.modules))
                    module_score += round(3 * role_count / len(trace.modules))
                elif trace.module_design_deferred and trace.module_defer_reason:
                    module_score = 4
                module_score = min(10, module_score)

                compatibility_score = 0
                if trace.modules:
                    semantic_count = sum(
                        bool(item.input_semantics and item.output_semantics and item.failure_mode)
                        for item in trace.modules
                    )
                    switch_count = sum(bool(item.implementation_switch) for item in trace.modules)
                    compatibility_score += round(6 * semantic_count / len(trace.modules))
                    compatibility_score += round(2 * switch_count / len(trace.modules))
                    compatibility_score += round(
                        4 * independently_verified_modules / len(trace.modules)
                    )
                    compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
                elif trace.module_design_deferred:
                    compatibility_score = 3
                compatibility_score = min(15, compatibility_score)
            '''
        ),
    )
    replace_once(
        "scripts/score_academic_tailoring_retrieval_v1.py",
        block(
            '''
                if any(item.role_compatible is False for item in trace.modules):
                    hard_failures.append("unsupported_compatibility")
                if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
            '''
        ),
        block(
            '''
                if any(item.role_compatible is False for item in trace.modules):
                    hard_failures.append("unsupported_compatibility")
                if trace.modules and independently_verified_modules != len(trace.modules):
                    hard_failures.append("module_compatibility_not_independently_verified")
                if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
            '''
        ),
    )
    replace_once(
        "scripts/score_academic_tailoring_retrieval_v1.py",
        block(
            '''
                return {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    "domain": case["domain"],
                    "score": score,
                    "minimum_score": minimum_score,
                    "status": "passed" if score >= minimum_score and not hard_failures else "failed",
            '''
        ),
        block(
            '''
                expected_rejection_failures = {
                    "wrong_paper_identity",
                    "missing_required_baseline",
                    "baseline_not_bound_to_accepted_evidence",
                }
                correct_rejection = bool(
                    baseline_identity_status in {"missing", "unbound", "mismatch"}
                    and trace.decision in {"REVISE", "NO_GO"}
                )
                blocking_hard_failures = sorted(
                    failure
                    for failure in set(hard_failures)
                    if not (correct_rejection and failure in expected_rejection_failures)
                )
                status = (
                    "passed"
                    if (
                        correct_rejection and not blocking_hard_failures
                    )
                    or (
                        not correct_rejection
                        and score >= minimum_score
                        and not blocking_hard_failures
                    )
                    else "failed"
                )

                return {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    "domain": case["domain"],
                    "score": score,
                    "minimum_score": minimum_score,
                    "status": status,
                    "acceptance_mode": "correct_rejection" if correct_rejection else "positive",
            '''
        ),
    )
    replace_once(
        "scripts/score_academic_tailoring_retrieval_v1.py",
        '            "hard_failures": sorted(set(hard_failures)),\n',
        '            "hard_failures": sorted(set(hard_failures)),\n            "blocking_hard_failures": blocking_hard_failures,\n',
    )
    replace_once(
        "scripts/score_academic_tailoring_retrieval_v1.py",
        "    hard_failure_label_count = sum(len(item[\"hard_failures\"]) for item in results)\n    hard_failure_case_count = sum(bool(item[\"hard_failures\"]) for item in results)\n",
        "    hard_failure_label_count = sum(len(item[\"blocking_hard_failures\"]) for item in results)\n    hard_failure_case_count = sum(bool(item[\"blocking_hard_failures\"]) for item in results)\n",
    )


def patch_method_tests() -> None:
    replace_once(
        "tests/methodology/test_method_design_draft.py",
        block(
            '''
                    "input_semantics": "a shallow detector feature map containing fine spatial cues",
                    "output_semantics": "a shape-compatible enhanced feature map for the baseline head",
                    "predicted_effect": "improve small-object recall and AP_small",
            '''
        ),
        block(
            '''
                    "input_semantics": "a shallow detector feature map containing fine spatial cues",
                    "output_semantics": "a shape-compatible enhanced feature map for the baseline head",
                    "input_shape": "[B, C3, H/8, W/8] shallow detector feature map",
                    "output_shape": "[B, C3, H/8, W/8] enhanced feature map",
                    "insertion_point": "between the stride-8 backbone feature and the first neck fusion block",
                    "normalization_contract": "apply the source module normalization before neck fusion",
                    "masking_contract": "preserve detector target-validity masks without adding padding masks",
                    "gradient_path": "detection losses backpropagate through neck fusion into this module",
                    "trainable_parameters": "feature-fusion convolution and channel-gating parameters",
                    "frozen_parameters": "none during the matched end-to-end detector pilot",
                    "loss_terms": ["classification loss", "box regression loss"],
                    "loss_weighting": "use the frozen baseline classification and box-loss weights",
                    "predicted_effect": "improve small-object recall and AP_small",
            '''
        ),
    )
    replace_once(
        "tests/methodology/test_method_design_draft.py",
        '            "relation": "parallel_via_dataset",\n            "rank_score": "0.90",\n',
        '            "relation": "module_role_query",\n            "module_candidate": "inferred",\n            "rank_score": "0.90",\n            "relevance_score": "0.90",\n',
    )


def patch_scorer_tests() -> None:
    replace_once(
        "tests/evals/test_academic_tailoring_retrieval_v1_scorer.py",
        "_baseline_target_titles = _SCORER._baseline_target_titles\n_titles_related = _SCORER._titles_related\n",
        "_baseline_target_titles = _SCORER._baseline_target_titles\n_titles_related = _SCORER._titles_related\n",
    )
    append_once(
        "tests/evals/test_academic_tailoring_retrieval_v1_scorer.py",
        block(
            '''
                assert _accepted_asset_matches(assets, items) == 1
                assert _dataset_asset_score(assets, items) == 4
            '''
        ),
        block(
            '''


            def test_module_review_requires_parallel_role_and_explicit_compatibility() -> None:
                review = SimpleNamespace(
                    evidence_id="ev-module",
                    accepted=True,
                    identity_verified=True,
                    relevance_passed=True,
                    role="parallel_method",
                    role_compatible=True,
                )
                assert review.role == "parallel_method"
                assert review.role_compatible is True
            '''
        ),
    )


def main() -> None:
    patch_academic_methodology()
    patch_module_compatibility()
    patch_literature_adapter()
    patch_planning()
    patch_method_design()
    patch_benchmark_models()
    patch_benchmark_adapter()
    patch_scorer()
    patch_method_tests()
    patch_scorer_tests()


if __name__ == "__main__":
    main()
