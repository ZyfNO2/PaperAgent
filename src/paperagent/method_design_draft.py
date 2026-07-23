from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import Field

from paperagent.academic_methodology import (
    BaselineCard,
    ExperimentArmType,
    ExperimentCard,
    FalsifiableHypothesis,
    MethodPlan,
    ModuleCard,
    ResearchContract,
)
from paperagent.academic_methodology import (
    EvidenceItem as MethodEvidenceItem,
)
from paperagent.module_compatibility import (
    MODULE_EVIDENCE_RELATIONS,
    evaluate_module_compatibility,
)
from paperagent.schemas.base import FrozenModel
from paperagent.schemas.evidence import EvidenceItem
from paperagent.schemas.method import (
    AblationPlan,
    BaselineProposal,
    ExperimentPlan,
    IntegrationContract,
    MethodModule,
    MethodProposal,
)
from paperagent.scientific_readiness import derive_scientific_readiness
from paperagent.state import PaperAgentState


class MethodDesignDraft(FrozenModel):
    """Low-nesting LLM surface for method design.

    Provenance, experiment fairness, implementation switches, baseline parity,
    and duplicated legacy fields are created by the server after validation.
    """

    problem_method_insight: str = Field(min_length=10)
    proposed_method_summary: str = Field(min_length=10)
    condition: str = Field(min_length=5)
    limitation: str = Field(min_length=5)
    mechanism: str = Field(min_length=5)
    intervention: str = Field(min_length=5)
    predicted_metric_change: str = Field(min_length=5)
    guardrail: str = Field(min_length=5)
    module_name: str = Field(min_length=2, max_length=120)
    module_original_role: str = Field(min_length=3)
    module_proposed_role: str = Field(min_length=3)
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
    failure_mode: str = Field(min_length=5)
    compute_cost: str = Field(min_length=3)
    primary_metric: str = Field(min_length=2, max_length=80)
    resource_measures: list[str] = Field(min_length=1, max_length=8)
    stopping_criteria: str = Field(min_length=5)
    reported_dataset: str | None = None
    reported_comparator: str | None = None
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and value not in output:
            output.append(value)
    return tuple(output)


def _dedupe_list(values: Iterable[str]) -> list[str]:
    return list(_dedupe(values))


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return normalized[:48] or "candidate_module"


_DECLARED_ROLE_SUFFIX = re.compile(r"\s*\[declared role:(?P<role>[^\]]+)\]\s*$", re.IGNORECASE)


def _title_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _is_exact_acronym_alias(alias: str, full_title: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]+", "", alias)
    full_tokens = _title_tokens(full_title)
    return (
        len(compact) >= 3
        and compact.isupper()
        and bool(full_tokens)
        and compact.casefold() == full_tokens[0]
    )


def _titles_equivalent(left: str, right: str) -> bool:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if _is_exact_acronym_alias(left, right) or _is_exact_acronym_alias(right, left):
        return True
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    union = left_set | right_set
    overlap = left_set & right_set
    length_ratio = min(len(left_set), len(right_set)) / max(len(left_set), len(right_set))
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75


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


def _select_declared_baseline_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    declared_titles = _declared_baseline_titles(references)
    for declared_title in declared_titles:
        for item in candidates:
            if item.source_type == "paper" and _titles_equivalent(item.title, declared_title):
                return item
    return None


def _baseline_evidence_rank(item: EvidenceItem) -> tuple[int, int, float, str]:
    if item.source_type != "paper":
        return (-1, -1, -1.0, item.evidence_id)
    marker = item.metadata.get("baseline_candidate", "")
    relation = item.metadata.get("relation", "")
    marker_rank = {"declared": 3, "inferred": 2}.get(marker, 0)
    relation_rank = {
        "declared_identity": 4,
        "baseline_role_query": 3,
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
        and item.metadata.get("relation") in {"baseline_role_query", "parallel_via_dataset"}
    )
    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)


def _select_repository_backed_direct_baseline(
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    """Select a verified task paper with an accepted author-linked repository.

    This is a last-resort baseline when neither a declared-title match nor
    focused baseline retrieval produced an accepted candidate.
    """

    repository_parent_ids: set[str] = {
        parent_id
        for item in candidates
        if item.source_type == "repository"
        and item.metadata.get("relation") == "author_linked_from_verified_paper"
        for parent_id in (item.metadata.get("parent_paper_id"),)
        if parent_id
    }
    papers = tuple(
        item
        for item in candidates
        if item.source_type == "paper"
        and item.metadata.get("relation") == "direct_query"
        and item.evidence_id.removeprefix("ev-") in repository_parent_ids
        and not _is_review_evidence(item.title, item.summary)
    )
    if not papers:
        return None
    return max(papers, key=_baseline_evidence_rank)


def _comparator_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
    if item.source_type != "paper":
        return (-1, -1.0, item.evidence_id)
    marker_rank = int(item.metadata.get("comparator_candidate") == "inferred")
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (marker_rank, rank_score, item.evidence_id)


def _select_inferred_comparator_evidence(
    candidates: tuple[EvidenceItem, ...],
    *,
    excluded_ids: set[str],
) -> EvidenceItem | None:
    papers = tuple(
        item
        for item in candidates
        if item.source_type == "paper"
        and item.evidence_id not in excluded_ids
        and item.metadata.get("comparator_candidate") == "inferred"
        and item.metadata.get("relation") == "comparator_role_query"
    )
    if not papers:
        return None
    return max(papers, key=_comparator_evidence_rank)


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


def _question_declares_dataset(question: str) -> bool:
    return bool(
        re.search(r"\b(?:datasets?|benchmarks?|corpus|corpora|data[ -]?set)\b", question, re.I)
    )


def _dataset_plan_value(
    question: str,
    *,
    readiness_confirmed: bool,
) -> str:
    if readiness_confirmed:
        return "user-declared frozen dataset; preserve the exact identifier and fingerprint"
    if _question_declares_dataset(question):
        return (
            "declared dataset identity unresolved; verify the exact dataset, split, license, "
            "and fingerprint before the pilot"
        )
    return (
        "unresolved task-matched data source; no public dataset is required at "
        "discovery time; use task-appropriate user-owned, "
        "synthetic, simulated, or newly collected data and freeze provenance, split, license, "
        "and fingerprint before execution"
    )


def _dataset_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
    relation = item.metadata.get("relation", "")
    relation_rank = {
        "dataset_linked_by_focused_retrieval": 2,
        "dataset_named_in_verified_paper": 1,
    }.get(relation, 0)
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (relation_rank, rank_score, item.evidence_id)


def _select_dataset_evidence(
    question: str, candidates: tuple[EvidenceItem, ...]
) -> EvidenceItem | None:
    datasets = tuple(item for item in candidates if item.source_type == "dataset")
    normalized_question = question.casefold()
    explicit = tuple(
        item
        for item in datasets
        if re.search(
            rf"(?<![a-z0-9]){re.escape(item.title.casefold())}(?![a-z0-9])",
            normalized_question,
        )
    )
    if explicit:
        return max(explicit, key=_dataset_evidence_rank)
    linked = tuple(
        item
        for item in datasets
        if item.metadata.get("relation") == "dataset_linked_by_focused_retrieval"
    )
    if linked:
        return max(linked, key=_dataset_evidence_rank)
    return None


def _evidence_text(state: PaperAgentState) -> str:
    evidence = state.get("evidence")
    if evidence is None:
        return ""
    return "\n".join(f"{item.title}\n{item.summary}" for item in evidence.accepted_items())


def _grounded_optional(value: str | None, evidence_text: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized if normalized.casefold() in evidence_text.casefold() else None


def _select_reported_comparator_evidence(
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


def _metadata_text(metadata: dict[str, str], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _is_review_evidence(title: str, summary: str) -> bool:
    text = f"{title} {summary}".casefold()
    return any(cue in text for cue in ("review", "survey", "taxonomy"))


def _hypothesis_sentence(draft: MethodDesignDraft) -> str:
    return (
        f"Under {draft.condition}, {draft.intervention} should "
        f"{draft.predicted_metric_change} because {draft.mechanism} addresses "
        f"{draft.limitation}, while {draft.guardrail}."
    )


def _canonical_evidence(state: PaperAgentState) -> tuple[MethodEvidenceItem, ...]:
    evidence = state.get("evidence")
    if evidence is None:
        return ()
    return tuple(
        MethodEvidenceItem(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            title=item.title,
            stable_identifier=item.stable_identifier,
            verified=True,
            supported_claims=(item.summary,),
            limitations=(),
            content_hash=item.content_hash,
            license=_metadata_text(item.metadata, "license"),
            repository_ref=_metadata_text(item.metadata, "repository_ref"),
        )
        for item in evidence.accepted_items()
    )


def _experiment(
    *,
    name: str,
    arm_type: ExperimentArmType,
    included_modules: tuple[str, ...],
    source_evidence_id: str | None,
    comparator: str,
    purpose: str,
    contrast: str,
    dataset: str,
    metrics: tuple[str, ...],
    resource_measures: tuple[str, ...],
    stopping_criteria: str,
) -> ExperimentCard:
    return ExperimentCard(
        name=name,
        arm_type=arm_type,
        included_modules=included_modules,
        source_evidence_id=source_evidence_id,
        comparator=comparator,
        dataset=dataset,
        split="freeze the official or documented train/validation/test split before the pilot",
        preprocessing=(
            "match input construction, preprocessing, normalization, post-processing, "
            "and inference precision across arms"
        ),
        tuning_budget=(
            "match epochs or steps, optimizer search space, input budget, early stopping, "
            "and total compute"
        ),
        metrics=metrics,
        seeds=(1, 2, 3),
        uncertainty_reporting="report mean, standard deviation, and confidence intervals",
        resource_measures=resource_measures,
        purpose=purpose,
        contrast=contrast,
        stopping_criteria=stopping_criteria,
    )


def build_method_proposal(
    state: PaperAgentState,
    draft: MethodDesignDraft,
) -> MethodProposal:
    request = state.get("request")
    plan = state.get("plan")
    evidence_bundle = state.get("evidence")
    if request is None or plan is None or evidence_bundle is None:
        raise ValueError("request, research plan, and evidence are required")

    explicit = derive_scientific_readiness(request.question)
    invalid_protocol = (
        draft.explicit_evaluation_protocol_invalid or explicit.explicit_evaluation_protocol_invalid
    )
    draft = draft.model_copy(
        update={
            "baseline_readiness_confirmed": (
                draft.baseline_readiness_confirmed or explicit.baseline_readiness_confirmed
            ),
            "evaluation_protocol_validated": (
                (draft.evaluation_protocol_validated or explicit.evaluation_protocol_validated)
                and not invalid_protocol
            ),
            "comparison_readiness_confirmed": (
                draft.comparison_readiness_confirmed or explicit.comparison_readiness_confirmed
            ),
            "module_validation_confirmed": (
                draft.module_validation_confirmed or explicit.module_validation_confirmed
            ),
            "failure_policy_confirmed": (
                draft.failure_policy_confirmed or explicit.failure_policy_confirmed
            ),
            "explicit_evaluation_protocol_invalid": invalid_protocol,
        }
    )

    accepted = tuple(evidence_bundle.accepted_items())
    if not accepted:
        raise ValueError("method canonicalization requires accepted methodology evidence")
    attributed = tuple(
        item for item in accepted if not _is_review_evidence(item.title, item.summary)
    )
    method_evidence = attributed if attributed else accepted
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
    dataset_evidence = _select_dataset_evidence(request.question, accepted)
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
    if grounded_dataset is None and dataset_evidence is not None:
        grounded_dataset = dataset_evidence.title
    excluded_comparator_ids = {module_primary.evidence_id}
    if baseline_evidence is not None:
        excluded_comparator_ids.add(baseline_evidence.evidence_id)
    reported_comparator_evidence = _select_reported_comparator_evidence(
        draft.reported_comparator,
        accepted,
        excluded_ids=excluded_comparator_ids,
    )
    grounded_comparator = (
        reported_comparator_evidence.title if reported_comparator_evidence is not None else None
    )
    comparator_evidence_id = (
        reported_comparator_evidence.evidence_id
        if reported_comparator_evidence is not None
        else None
    )
    if draft.comparison_readiness_confirmed and (
        grounded_comparator is None or comparator_evidence_id is None
    ):
        comparator_evidence = _select_inferred_comparator_evidence(
            attributed,
            excluded_ids=excluded_comparator_ids,
        )
        if comparator_evidence is not None:
            grounded_comparator = comparator_evidence.title
            comparator_evidence_id = comparator_evidence.evidence_id

    baseline_identity_resolved = baseline_evidence is not None
    effective_baseline_readiness = draft.baseline_readiness_confirmed and baseline_identity_resolved
    readiness_confirmed = (
        effective_baseline_readiness
        and draft.evaluation_protocol_validated
        and not draft.explicit_evaluation_protocol_invalid
    )
    dataset = grounded_dataset or _dataset_plan_value(
        request.question,
        readiness_confirmed=readiness_confirmed,
    )
    baseline_unresolved = baseline_evidence is None
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
    baseline_stable_identifier = (
        baseline_evidence.stable_identifier if baseline_evidence is not None else "unresolved"
    )
    comparator = grounded_comparator if comparator_evidence_id is not None else None
    module_name = draft.module_name.strip()
    module_switch = f"enable_{_slug(module_name)}"
    plan_risks = tuple(plan.risks)

    contract = ResearchContract(
        target_problem=request.question,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=_dedupe((*request.required_constraints, *plan_risks)),
        intended_claim=draft.proposed_method_summary,
        observed_problem=draft.limitation,
        proposed_mechanism=draft.mechanism,
        baseline_readiness_confirmed=effective_baseline_readiness,
        evaluation_protocol_validated=draft.evaluation_protocol_validated,
        comparison_readiness_confirmed=draft.comparison_readiness_confirmed,
        module_validation_confirmed=draft.module_validation_confirmed,
        failure_policy_confirmed=draft.failure_policy_confirmed,
        explicit_evaluation_protocol_invalid=draft.explicit_evaluation_protocol_invalid,
    )
    baseline = BaselineCard(
        name=baseline_name,
        version_or_commit=(
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
                            f"{baseline_stable_identifier}; reproduce and freeze an "
                            "implementation before module integration"
                        )
                        if baseline_inferred and baseline_evidence is not None
                        else (
                            f"published source {baseline_stable_identifier}; "
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
        dataset=dataset,
        split=(
            "user-declared frozen independent split; preserve the exact split manifest"
            if readiness_confirmed
            else "not yet frozen; preserve the documented benchmark split and record data hashes"
        ),
        environment=(
            "user-declared frozen execution environment; preserve the exact environment manifest"
            if readiness_confirmed
            else (
                "not yet frozen; record hardware, framework, precision, export path, "
                "and dependency lock"
            )
        ),
        seed_policy="three fixed seeds (1, 2, 3) for all pilot comparisons",
        reproduced=readiness_confirmed,
        reproduced_metric=(
            f"user-declared reproduced {draft.primary_metric}; preserve the exact numeric result"
            if readiness_confirmed
            else None
        ),
        compute_fit=True if readiness_confirmed else None,
        baseline_parity_verified=(readiness_confirmed and draft.module_validation_confirmed),
        dataset_fingerprint=(
            "user-declared frozen dataset fingerprint; preserve the exact digest"
            if readiness_confirmed
            else None
        ),
        environment_fingerprint=(
            "user-declared frozen environment fingerprint; preserve the exact digest"
            if readiness_confirmed
            else None
        ),
    )
    hypothesis = FalsifiableHypothesis(
        condition=draft.condition,
        limitation=draft.limitation,
        mechanism=draft.mechanism,
        intervention=draft.intervention,
        predicted_metric_change=draft.predicted_metric_change,
        guardrail=draft.guardrail,
    )
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
        raise ValueError("module_design_deferred: " + ",".join(compatibility.reasons))
    metrics = _dedupe((draft.primary_metric, "latency"))
    resources = _dedupe((*draft.resource_measures, "parameters", "memory", "latency"))
    experiments = [
        _experiment(
            name="E0-frozen-baseline",
            arm_type=ExperimentArmType.BASELINE,
            included_modules=(),
            source_evidence_id=baseline_source_evidence_id,
            comparator=baseline_name,
            purpose="establish a reproducible task-matched baseline under frozen settings",
            contrast="baseline only",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
        _experiment(
            name="E1-single-module",
            arm_type=ExperimentArmType.SINGLE_MODULE,
            included_modules=(module_name,),
            source_evidence_id=module_primary.evidence_id,
            comparator=baseline_name,
            purpose="isolate the causal contribution of the proposed module",
            contrast=f"{module_name} enabled versus the frozen baseline",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
        _experiment(
            name="E2-full-method",
            arm_type=ExperimentArmType.FULL,
            included_modules=(module_name,),
            source_evidence_id=module_primary.evidence_id,
            comparator=baseline_name,
            purpose="measure the complete minimal method under the same evaluation contract",
            contrast="full minimal method versus baseline",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
    ]
    if comparator is not None and comparator_evidence_id is not None:
        experiments.append(
            _experiment(
                name="E3-strong-comparison",
                arm_type=ExperimentArmType.STRONG_COMPARISON,
                included_modules=(),
                source_evidence_id=comparator_evidence_id,
                comparator=comparator,
                purpose="test whether the contribution survives a stronger matched comparator",
                contrast="full method versus the evidence-bound strong comparison",
                dataset=dataset,
                metrics=metrics,
                resource_measures=resources,
                stopping_criteria=draft.stopping_criteria,
            )
        )
    stop_conditions = _dedupe(
        (
            draft.stopping_criteria,
            "stop if the target gain disappears under matched data and tuning",
            "revise if latency, memory, or compute guardrails fail on the selected device",
            "do not claim novelty if a stronger comparison implements the same mechanism",
        )
    )
    methodology_plan = MethodPlan(
        research=contract,
        evidence=_canonical_evidence(state),
        baseline=baseline,
        hypothesis=hypothesis,
        modules=(module,),
        experiments=tuple(experiments),
        stop_conditions=stop_conditions,
    )
    risks = _dedupe_list(
        (
            *plan_risks,
            plan.clarification_question or "",
            (
                "baseline identity is unresolved; retrieve and reproduce an evidence-bound "
                "task-matched comparator before claiming a baseline result"
                if baseline_unresolved
                else "baseline reproduction and disabled-module parity are not yet verified"
            ),
            "implementation and evidence licenses must be resolved before code reuse",
            (
                "a public dataset is optional for niche tasks, but any user-owned, synthetic, "
                "simulated, or newly collected data must be frozen with provenance before execution"
            ),
        )
    )
    hypothesis_text = _hypothesis_sentence(draft)
    evidence_ids = [item.evidence_id for item in accepted]

    return MethodProposal(
        baseline=BaselineProposal(
            name=baseline_name,
            description=(
                "Accepted evidence constrains baseline selection; implementation version, "
                "reproduction, and deployment fit remain pilot gates."
            ),
        ),
        modules=[
            MethodModule(
                module_id=module_name,
                name=module_name,
                purpose=draft.module_proposed_role,
            )
        ],
        integration_contracts=[
            IntegrationContract(
                from_module=draft.insertion_point,
                to_module=module_name,
                input=draft.input_semantics,
                output=draft.output_semantics,
            )
        ],
        problem_method_insight=draft.problem_method_insight,
        falsifiable_hypothesis=hypothesis_text,
        minimum_key_experiment=ExperimentPlan(
            name="matched frozen-baseline pilot",
            conditions=[
                "run the frozen baseline with the module disabled",
                f"run the same configuration with {module_switch}=true",
                "hold data, preprocessing, tuning budget, seeds, precision, and hardware fixed",
            ],
            metrics=list(metrics),
            baseline=baseline_name,
            success_threshold=draft.stopping_criteria,
        ),
        ablations=[
            AblationPlan(
                name="module-off parity",
                change=f"set {module_switch}=false",
                expected_observation="recover the unchanged frozen baseline path",
            ),
            AblationPlan(
                name="single-module causal test",
                change=f"enable only {module_name} under the matched budget",
                expected_observation=draft.predicted_effect,
            ),
        ],
        risks=risks,
        stop_conditions=list(stop_conditions),
        evidence_ids=evidence_ids,
        methodology_plan=methodology_plan,
    )


__all__ = ["MethodDesignDraft", "build_method_proposal"]
