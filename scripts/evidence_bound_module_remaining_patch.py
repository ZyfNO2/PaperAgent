from __future__ import annotations

from pathlib import Path

from evidence_bound_module_prepatch import replace_exact

ACADEMIC = Path("src/paperagent/academic_methodology.py")
LITERATURE = Path("src/paperagent/literature/adapter.py")
PLANNING = Path("src/paperagent/nodes/planning.py")
BENCHMARK = Path("src/paperagent/claw_academic_benchmark.py")
ADAPTER = Path("src/paperagent/claw_benchmark_adapter.py")
SCORER = Path("scripts/score_academic_tailoring_retrieval_v1.py")
METHOD_TESTS = Path("tests/methodology/test_method_design_draft.py")


def patch_academic_methodology() -> None:
    replace_exact(
        ACADEMIC,
        '''class ModuleCard(BaseModel):
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
''',
        '''class ModuleCard(BaseModel):
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
    # Legacy aliases remain serializable for stored plans and clients.
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
''',
        "ModuleCard structured contract",
    )


def patch_literature_role_detection() -> None:
    replace_exact(
        LITERATURE,
        '''_COMPARATOR_ROLE_QUERY = re.compile(
    r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
    re.IGNORECASE,
)
_DATASET_CONTEXT = re.compile(
''',
        '''_COMPARATOR_ROLE_QUERY = re.compile(
    r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
    re.IGNORECASE,
)
_MODULE_ROLE_QUERY = re.compile(
    r"(?:\\bmodules?\\b|\\bparallel(?: method| paper)?\\b|\\bmechanisms?\\b|"
    r"模块|平行论文|并行方法|机制)",
    re.IGNORECASE,
)
_DATASET_CONTEXT = re.compile(
''',
        "module role query regex",
    )
    replace_exact(
        LITERATURE,
        '''def _query_seeks_comparator_role(query: str) -> bool:
    return not _query_seeks_baseline_role(query) and bool(_COMPARATOR_ROLE_QUERY.search(query))


def _query_candidate_role(query: str) -> str | None:
    if _query_seeks_baseline_role(query):
        return "baseline"
    if _query_seeks_comparator_role(query):
        return "comparator"
    return None
''',
        '''def _query_seeks_comparator_role(query: str) -> bool:
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
''',
        "module role query classification",
    )


def patch_planning_role_hints() -> None:
    replace_exact(
        PLANNING,
        "from __future__ import annotations\n\nfrom langchain_core.runnables import RunnableConfig\n",
        "from __future__ import annotations\n\nimport re\n\nfrom langchain_core.runnables import RunnableConfig\n",
        "planning regex import",
    )
    replace_exact(
        PLANNING,
        '''def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
    normalized_title = " ".join(title.replace('"', " ").split()).casefold()
    normalized_query = " ".join(query.query.replace('"', " ").split()).casefold()
    return bool(normalized_title and normalized_title in normalized_query)
''',
        '''def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
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
''',
        "planning material role helper",
    )


def patch_benchmark_models() -> None:
    replace_exact(
        BENCHMARK,
        '''    implementation_switch: str | None = None
    role_compatible: bool | None = None
''',
        '''    implementation_switch: str | None = None
    role_compatible: bool | None = None
    compatibility_reasons: tuple[str, ...] = ()
''',
        "ModuleTrace compatibility reasons",
    )


def patch_benchmark_adapter() -> None:
    replace_exact(
        ADAPTER,
        "from paperagent.academic_methodology import ExperimentArmType\n",
        '''from paperagent.academic_methodology import ExperimentArmType
from paperagent.module_compatibility import (
    ModuleCompatibilityResult,
    evaluate_module_compatibility,
)
''',
        "benchmark adapter compatibility import",
    )
    marker = '''def _method_evidence_roles(state: PaperAgentState) -> dict[str, EvidenceRole]:
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
    addition = '''


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
    text = ADAPTER.read_text(encoding="utf-8")
    if "def _module_compatibility_by_evidence" not in text:
        if text.count(marker) != 1:
            raise RuntimeError("benchmark adapter method role helper shape changed")
        ADAPTER.write_text(text.replace(marker, marker + addition), encoding="utf-8")

    replace_exact(
        ADAPTER,
        '''    method_roles = _method_evidence_roles(state)
    full_text_ids = set(context.full_text_evidence_ids)
''',
        '''    method_roles = _method_evidence_roles(state)
    module_compatibility = _module_compatibility_by_evidence(state)
    full_text_ids = set(context.full_text_evidence_ids)
''',
        "benchmark adapter review compatibility map",
    )
    replace_exact(
        ADAPTER,
        '''                source_is_supplied_material=item.source_type == "user_material",
                role_compatible=None,
''',
        '''                source_is_supplied_material=item.source_type == "user_material",
                role_compatible=(
                    module_compatibility[item.evidence_id].compatible
                    if role == "parallel_method" and item.evidence_id in module_compatibility
                    else None
                ),
''',
        "benchmark evidence review compatibility",
    )
    replace_exact(
        ADAPTER,
        '''def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
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
''',
        '''def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
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
                role_compatible=compatibility.compatible if compatibility is not None else False,
                compatibility_reasons=(
                    compatibility.reasons
                    if compatibility is not None
                    else ("module_evidence_missing",)
                ),
            )
        )
    return tuple(output)
''',
        "benchmark module compatibility trace",
    )


def patch_scorer() -> None:
    text = SCORER.read_text(encoding="utf-8")
    if "_REJECTION_CASE_IDS" not in text:
        insert = '''_REJECTION_CASE_IDS = frozenset(
    {
        "atr-v1-006-industrial-usad-anomaly-transformer",
        "atr-v1-010-rec-coldstart-sequential",
    }
)
'''
        anchor = '''_INFERRED_BASELINE_RELATIONS = frozenset(
    {
        "baseline_role_query",
        "parallel_via_dataset",
        "direct_query",
    }
)
'''
        if text.count(anchor) != 1:
            raise RuntimeError("scorer relation constants shape changed")
        SCORER.write_text(text.replace(anchor, anchor + insert), encoding="utf-8")

    replace_exact(
        SCORER,
        '''    valid_evidence_ids = set(accepted_items_by_id)
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
''',
        '''    valid_evidence_ids = set(accepted_items_by_id)
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
        compatibility_score += round(4 * independently_verified_modules / len(trace.modules))
        compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
    elif trace.module_design_deferred:
        compatibility_score = 3
    compatibility_score = min(15, compatibility_score)
''',
        "scorer independent compatibility scoring",
    )
    replace_exact(
        SCORER,
        '''    if any(item.role_compatible is False for item in trace.modules):
        hard_failures.append("unsupported_compatibility")
    if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
''',
        '''    if any(item.role_compatible is False for item in trace.modules):
        hard_failures.append("unsupported_compatibility")
    if trace.modules and independently_verified_modules != len(trace.modules):
        hard_failures.append("module_compatibility_not_independently_verified")
    if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
''',
        "scorer independent compatibility hard failure",
    )
    replace_exact(
        SCORER,
        '''    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "domain": case["domain"],
        "score": score,
        "minimum_score": minimum_score,
        "status": "passed" if score >= minimum_score and not hard_failures else "failed",
''',
        '''    rejection_expected = str(case["case_id"]) in _REJECTION_CASE_IDS
    correct_rejection = bool(
        rejection_expected
        and baseline_identity_status in {"missing", "unbound", "mismatch"}
        and trace.decision in {"REVISE", "NO_GO"}
    )
    expected_rejection_failures = {
        "wrong_paper_identity",
        "missing_required_baseline",
        "baseline_not_bound_to_accepted_evidence",
    }
    blocking_hard_failures = sorted(
        failure
        for failure in set(hard_failures)
        if not (correct_rejection and failure in expected_rejection_failures)
    )
    status = (
        "passed"
        if (correct_rejection and not blocking_hard_failures)
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
''',
        "scorer rejection acceptance",
    )
    replace_exact(
        SCORER,
        '''        "hard_failures": sorted(set(hard_failures)),
''',
        '''        "hard_failures": sorted(set(hard_failures)),
        "blocking_hard_failures": blocking_hard_failures,
''',
        "scorer blocking hard failures",
    )
    replace_exact(
        SCORER,
        '''    hard_failure_label_count = sum(len(item["hard_failures"]) for item in results)
    hard_failure_case_count = sum(bool(item["hard_failures"]) for item in results)
''',
        '''    hard_failure_label_count = sum(len(item["blocking_hard_failures"]) for item in results)
    hard_failure_case_count = sum(bool(item["blocking_hard_failures"]) for item in results)
''',
        "scorer aggregate blocking failures",
    )


def patch_method_tests() -> None:
    replace_exact(
        METHOD_TESTS,
        '_EVIDENCE_ID = "ev-drone-detr"\n',
        '_EVIDENCE_ID = "ev-drone-detr"\n_BASELINE_ID = "ev-rt-detr-baseline"\n',
        "method test baseline id",
    )
    replace_exact(
        METHOD_TESTS,
        '''def _support(gap_id: str, claim: str) -> GapSupportAssessment:
    return GapSupportAssessment(
        evidence_id=_EVIDENCE_ID,
''',
        '''def _support(
    gap_id: str,
    claim: str,
    *,
    evidence_id: str = _EVIDENCE_ID,
) -> GapSupportAssessment:
    return GapSupportAssessment(
        evidence_id=evidence_id,
''',
        "method test support evidence id",
    )
    replace_exact(
        METHOD_TESTS,
        '''            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.90",
''',
        '''            "module_candidate": "inferred",
            "relation": "module_role_query",
            "rank_score": "0.90",
            "relevance_score": "0.90",
''',
        "method test module metadata",
    )
    anchor = '''    support = (
        _support(baseline_gap.gap_id, baseline_gap.description),
        _support(mechanism_gap.gap_id, mechanism_gap.description),
    )
'''
    baseline_item = '''    baseline_item = EvidenceItem(
        evidence_id=_BASELINE_ID,
        source_type="paper",
        title="RT-DETR-R18 baseline for small object detection",
        locator="doi:10.1000/rt-detr-baseline",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[baseline_gap.gap_id],
        summary="RT-DETR-R18 is a task-matched detector baseline with a verified paper identity.",
        content_hash="sha256:rt-detr-baseline",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/rt-detr-baseline",
            "baseline_candidate": "inferred",
            "relation": "baseline_role_query",
            "rank_score": "0.92",
            "relevance_score": "0.90",
            "license": "CC BY 4.0",
        },
    )
    support = (
        _support(baseline_gap.gap_id, baseline_gap.description),
        _support(mechanism_gap.gap_id, mechanism_gap.description),
    )
    baseline_support = _support(
        baseline_gap.gap_id,
        "RT-DETR-R18 supplies the independent baseline identity.",
        evidence_id=_BASELINE_ID,
    )
'''
    replace_exact(METHOD_TESTS, anchor, baseline_item, "method test baseline evidence")
    replace_exact(
        METHOD_TESTS,
        '''        entries=(
            EvidenceLedgerEntry(
                evidence_id=_EVIDENCE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=support,
                supported_claims=tuple(item.supported_claim or "" for item in support),
                limitations=("pilot reproduction remains required",),
                accepted=True,
                rejection_reasons=(),
            ),
        ),
        accepted_ids=(_EVIDENCE_ID,),
''',
        '''        entries=(
            EvidenceLedgerEntry(
                evidence_id=_EVIDENCE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=support,
                supported_claims=tuple(item.supported_claim or "" for item in support),
                limitations=("pilot reproduction remains required",),
                accepted=True,
                rejection_reasons=(),
            ),
            EvidenceLedgerEntry(
                evidence_id=_BASELINE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=(baseline_support,),
                supported_claims=(baseline_support.supported_claim or "",),
                limitations=("pilot reproduction remains required",),
                accepted=True,
                rejection_reasons=(),
            ),
        ),
        accepted_ids=(_EVIDENCE_ID, _BASELINE_ID),
''',
        "method test evidence ledger",
    )
    replace_exact(
        METHOD_TESTS,
        '''            "evidence": EvidenceBundle(
                items=[evidence_item],
                accepted_ids=[_EVIDENCE_ID],
                identity_verified_ids=[_EVIDENCE_ID],
''',
        '''            "evidence": EvidenceBundle(
                items=[evidence_item, baseline_item],
                accepted_ids=[_EVIDENCE_ID, _BASELINE_ID],
                identity_verified_ids=[_EVIDENCE_ID, _BASELINE_ID],
''',
        "method test evidence bundle",
    )
    replace_exact(
        METHOD_TESTS,
        '''        "input_semantics": "a shallow detector feature map containing fine spatial cues",
        "output_semantics": "a shape-compatible enhanced feature map for the baseline head",
        "predicted_effect": "improve small-object recall and AP_small",
''',
        '''        "input_semantics": "a shallow backbone feature map containing fine spatial cues",
        "output_semantics": "a shape-compatible enhanced feature map for the baseline neck",
        "input_shape": "[B, C3, H/8, W/8] shallow backbone feature map",
        "output_shape": "[B, C3, H/8, W/8] enhanced feature map",
        "insertion_point": "between the stride-8 backbone feature and the first neck fusion block",
        "normalization_contract": "apply source-paper channel normalization before neck fusion",
        "masking_contract": "preserve target-validity masks without adding padding-mask semantics",
        "gradient_path": "detection losses backpropagate through the neck into fusion parameters",
        "trainable_parameters": "feature-fusion convolution and channel-gating parameters",
        "frozen_parameters": "none during the matched end-to-end detector pilot",
        "loss_terms": ["classification loss", "box regression loss"],
        "loss_weighting": "classification weight 1.0 and box regression weight 5.0",
        "predicted_effect": "improve small-object recall and AP_small",
''',
        "method test structured draft",
    )
    replace_exact(
        METHOD_TESTS,
        '    assert set(proposal.evidence_ids) == {_EVIDENCE_ID}\n',
        '    assert set(proposal.evidence_ids) == {_EVIDENCE_ID, _BASELINE_ID}\n',
        "method test evidence ids",
    )
    replace_exact(
        METHOD_TESTS,
        '''            "metadata": {
                "doi": "10.1007/s00500-024-09901-x",
                "candidate_gap_ids": "baseline_comparison,failure_mechanism",
            },
''',
        '''            "metadata": {
                "doi": "10.1007/s00500-024-09901-x",
                "candidate_gap_ids": "baseline_comparison,failure_mechanism",
                "module_candidate": "inferred",
                "relation": "module_role_query",
                "rank_score": "0.91",
                "relevance_score": "0.88",
            },
''',
        "medical module test metadata",
    )
    replace_exact(
        METHOD_TESTS,
        '''            "evidence": evidence.model_copy(update={"items": [medical_item]}),
''',
        '''            "evidence": evidence.model_copy(update={"items": [medical_item, evidence.items[1]]}),
''',
        "medical test baseline preservation",
    )
    replace_exact(
        METHOD_TESTS,
        '''    direct_item = evidence.items[0].model_copy(
''',
        '''    direct_item = evidence.items[1].model_copy(
''',
        "direct baseline test source",
    )
    replace_exact(
        METHOD_TESTS,
        '''            "evidence": evidence.model_copy(update={"items": [direct_item]}),
''',
        '''            "evidence": evidence.model_copy(update={"items": [evidence.items[0], direct_item]}),
''',
        "direct baseline test module preservation",
    )


def apply_remaining() -> None:
    patch_academic_methodology()
    patch_literature_role_detection()
    patch_planning_role_hints()
    patch_benchmark_models()
    patch_benchmark_adapter()
    patch_scorer()
    patch_method_tests()


if __name__ == "__main__":
    apply_remaining()
