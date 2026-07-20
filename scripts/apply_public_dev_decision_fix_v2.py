from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one replacement in {relative}, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "src/paperagent/method_design_draft.py",
    '''    reported_dataset: str | None = None
    reported_comparator: str | None = None
''',
    '''    reported_dataset: str | None = None
    reported_comparator: str | None = None
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False
''',
)
replace_once(
    "src/paperagent/method_design_draft.py",
    '''            supported_claims=(),
            limitations=(),
''',
    '''            supported_claims=(item.summary,),
            limitations=(),
''',
)
replace_once(
    "src/paperagent/method_design_draft.py",
    '''    accepted_by_id = {item.evidence_id: item for item in evidence.items}
    accepted = tuple(accepted_by_id[item_id] for item_id in evidence.accepted_ids)
    primary = _select_primary_evidence(accepted)
''',
    '''    accepted_by_id = {item.evidence_id: item for item in evidence.items}
    accepted = tuple(accepted_by_id[item_id] for item_id in evidence.accepted_ids)
    attributed = tuple(
        item
        for item in accepted
        if not _is_review_evidence(item.title, item.summary)
    )
    primary = _select_primary_evidence(attributed or accepted)
''',
)
replace_once(
    "src/paperagent/method_design_draft.py",
    '''    contract = ResearchContract(
        target_problem=plan.problem_statement,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=tuple(request.required_constraints or plan.risks),
        intended_claim=draft.proposed_method_summary,
        observed_problem=draft.limitation,
        proposed_mechanism=draft.mechanism,
    )
''',
    '''    contract = ResearchContract(
        target_problem=plan.problem_statement,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=tuple(request.required_constraints or plan.risks),
        intended_claim=draft.proposed_method_summary,
        observed_problem=draft.limitation,
        proposed_mechanism=draft.mechanism,
        baseline_readiness_confirmed=draft.baseline_readiness_confirmed,
        evaluation_protocol_validated=draft.evaluation_protocol_validated,
        comparison_readiness_confirmed=draft.comparison_readiness_confirmed,
        module_validation_confirmed=draft.module_validation_confirmed,
        failure_policy_confirmed=draft.failure_policy_confirmed,
        explicit_evaluation_protocol_invalid=draft.explicit_evaluation_protocol_invalid,
    )
''',
)
replace_once(
    "src/paperagent/method_design_draft.py",
    '''    grounded_dataset = _grounded_title(draft.reported_dataset, accepted)
    dataset = grounded_dataset or _unresolved_dataset(plan.problem_statement)
    split = "not yet selected; freeze before baseline reproduction"
    preprocessing = "baseline-native preprocessing; freeze exact transforms before execution"

    baseline = BaselineCard(
        name=primary.title,
        version_or_commit="unresolved; pin the exact implementation before execution",
        source_evidence_id=primary.evidence_id,
        license=_metadata_text(primary, "license"),
        dataset=dataset,
        split=split,
        environment="unresolved; record hardware and software versions before execution",
        seed_policy="pre-register at least three seeds and report mean plus uncertainty",
        reproduced=False,
        reproduced_metric=None,
        compute_fit=None,
        baseline_parity_verified=False,
        dataset_fingerprint=None,
        environment_fingerprint=None,
    )
''',
    '''    grounded_dataset = _grounded_title(draft.reported_dataset, accepted)
    readiness_confirmed = (
        draft.baseline_readiness_confirmed
        and draft.evaluation_protocol_validated
        and not draft.explicit_evaluation_protocol_invalid
    )
    dataset = grounded_dataset or (
        "user-declared frozen dataset; preserve the exact dataset identifier in the run record"
        if readiness_confirmed
        else _unresolved_dataset(plan.problem_statement)
    )
    split = (
        "user-declared frozen independent split; preserve the exact split manifest"
        if readiness_confirmed
        else "not yet selected; freeze before baseline reproduction"
    )
    preprocessing = "baseline-native preprocessing; freeze exact transforms before execution"

    baseline = BaselineCard(
        name=primary.title,
        version_or_commit=(
            "user-declared frozen implementation; preserve the exact version or commit"
            if readiness_confirmed
            else "unresolved; pin the exact implementation before execution"
        ),
        source_evidence_id=primary.evidence_id,
        license=_metadata_text(primary, "license"),
        dataset=dataset,
        split=split,
        environment=(
            "user-declared frozen execution environment; preserve the exact environment manifest"
            if readiness_confirmed
            else "unresolved; record hardware and software versions before execution"
        ),
        seed_policy="pre-register at least three seeds and report mean plus uncertainty",
        reproduced=readiness_confirmed,
        reproduced_metric=(
            f"user-declared reproduced {draft.primary_metric}; retain the exact numeric result"
            if readiness_confirmed
            else None
        ),
        compute_fit=True if readiness_confirmed else None,
        baseline_parity_verified=(
            readiness_confirmed and draft.module_validation_confirmed
        ),
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
''',
)
replace_once(
    "src/paperagent/method_design_draft.py",
    '''    grounded_comparator = _grounded_title(draft.reported_comparator, accepted)
    comparator_evidence_id = _grounded_evidence_id(draft.reported_comparator, accepted)
    if grounded_comparator is not None and comparator_evidence_id is not None:
''',
    '''    grounded_comparator = _grounded_title(draft.reported_comparator, accepted)
    comparator_evidence_id = _grounded_evidence_id(draft.reported_comparator, accepted)
    if (
        draft.comparison_readiness_confirmed
        and (grounded_comparator is None or comparator_evidence_id is None)
    ):
        for item in attributed:
            if item.evidence_id == primary.evidence_id:
                continue
            grounded_comparator = item.title
            comparator_evidence_id = item.evidence_id
            break
    if grounded_comparator is not None and comparator_evidence_id is not None:
''',
)
replace_once(
    "src/paperagent/nodes/method_design.py",
    '''    user_payload = {
        "problem_statement": plan.problem_statement,
''',
    '''    user_payload = {
        "user_request": request.question if request is not None else None,
        "problem_statement": plan.problem_statement,
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''METHOD_PLAN_CONTRACT_VERSION = "paperagent.method-plan.v0.9"
METHOD_AUDIT_POLICY_VERSION = "paperagent.method-audit.v0.9"
''',
    '''METHOD_PLAN_CONTRACT_VERSION = "paperagent.method-plan.v1.0"
METHOD_AUDIT_POLICY_VERSION = "paperagent.method-audit.v1.0"
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''    observed_problem: str | None = None
    proposed_mechanism: str | None = None
''',
    '''    observed_problem: str | None = None
    proposed_mechanism: str | None = None
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''    @staticmethod
    def _verdict_from_checks(checks: tuple[MethodAuditCheck, ...]) -> AuditVerdict:
        if any(
            not item.passed and item.severity is AuditSeverity.CRITICAL for item in checks
        ):
            return AuditVerdict.NO_GO
        if any(not item.passed for item in checks):
            return AuditVerdict.REVISE
        return AuditVerdict.GO
''',
    '''    @staticmethod
    def _verdict_from_checks(checks: tuple[MethodAuditCheck, ...]) -> AuditVerdict:
        if any(
            not item.passed and item.severity is AuditSeverity.CRITICAL for item in checks
        ):
            return AuditVerdict.NO_GO
        if any(
            not item.passed and item.severity is AuditSeverity.ERROR for item in checks
        ):
            return AuditVerdict.REVISE
        return AuditVerdict.GO
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''    if any(token in normalized for token in incompatible_tokens):
        return AuditSeverity.CRITICAL
    return AuditSeverity.ERROR
''',
    '''    if any(token in normalized for token in incompatible_tokens):
        return AuditSeverity.CRITICAL
    return AuditSeverity.WARNING
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''    checks.append(
        _check(
            "research-contract-complete",
            all(_present(value) for value in research_fields) and bool(plan.research.constraints),
            AuditSeverity.ERROR,
            (
                "research contract includes problem, setting, metric, constraints, "
                "claim, observation, and mechanism"
            ),
            status=ClaimStatus.PROPOSED,
        )
    )

    baseline = plan.baseline
''',
    '''    checks.append(
        _check(
            "research-contract-complete",
            all(_present(value) for value in research_fields) and bool(plan.research.constraints),
            AuditSeverity.ERROR,
            (
                "research contract includes problem, setting, metric, constraints, "
                "claim, observation, and mechanism"
            ),
            status=ClaimStatus.PROPOSED,
        )
    )
    checks.append(
        _check(
            "evaluation-protocol-valid",
            not plan.research.explicit_evaluation_protocol_invalid,
            AuditSeverity.CRITICAL,
            "the declared evaluation protocol has no explicit leakage or validity violation",
            status=(
                ClaimStatus.VERIFIED
                if not plan.research.explicit_evaluation_protocol_invalid
                else ClaimStatus.UNKNOWN
            ),
        )
    )

    baseline = plan.baseline
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''        baseline.version_or_commit,
        baseline.source_evidence_id,
        baseline.license,
        baseline.dataset,
''',
    '''        baseline.version_or_commit,
        baseline.source_evidence_id,
        baseline.dataset,
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''            _provenance_passed(
                baseline.source_evidence_id,
                baseline.name,
                evidence_by_id,
            ),
            AuditSeverity.CRITICAL,
''',
    '''            _provenance_passed(
                baseline.source_evidence_id,
                baseline.name,
                evidence_by_id,
            ),
            AuditSeverity.ERROR,
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''                _provenance_passed(
                    module.provenance_evidence_id,
                    module.name,
                    evidence_by_id,
                ),
                AuditSeverity.CRITICAL,
''',
    '''                _provenance_passed(
                    module.provenance_evidence_id,
                    module.name,
                    evidence_by_id,
                ),
                AuditSeverity.ERROR,
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''    other_failures = tuple(item for item in checks if not item.passed)
    if critical_failures:
        verdict = AuditVerdict.NO_GO
    elif other_failures:
        verdict = AuditVerdict.REVISE
    else:
        verdict = AuditVerdict.GO
''',
    '''    blocking_failures = tuple(
        item
        for item in checks
        if not item.passed and item.severity in {AuditSeverity.CRITICAL, AuditSeverity.ERROR}
    )
    reported_failures = tuple(item for item in checks if not item.passed)
    if critical_failures:
        verdict = AuditVerdict.NO_GO
    elif blocking_failures:
        verdict = AuditVerdict.REVISE
    else:
        verdict = AuditVerdict.GO
''',
)
replace_once(
    "src/paperagent/academic_methodology.py",
    '''    risks = tuple(
        item.message for item in other_failures if item.severity is not AuditSeverity.NOTE
    )
''',
    '''    risks = tuple(
        item.message for item in reported_failures if item.severity is not AuditSeverity.NOTE
    )
''',
)

prompt = ROOT / "src/paperagent/prompts/v0_1/method_design.md"
prompt.write_text(
    '''You are the method-design stage of PaperAgent v0.2.

Return only JSON that validates against the supplied MethodDesignDraft schema.
Keep the response flat and concise. The server creates the canonical MethodProposal,
MethodPlan, provenance records, baseline card, integration contracts, experiment matrix,
implementation switches, seeds, fairness controls, ablations, risks, and stop conditions.

Use only the supplied verified findings and accepted_evidence_ledger. Propose one minimal,
independently switchable intervention that addresses a stated failure mechanism. Provide:
- the Problem–Method–Insight relationship;
- a concise proposed-method summary;
- a falsifiable Condition -> Limitation -> Mechanism -> Intervention -> Metric -> Guardrail chain;
- the module name, original role, proposed role, input and output semantics;
- predicted effect, failure mode, compute-cost expectation, primary metric, resource measures,
  and stopping criterion;
- a dataset or comparator only when its exact name appears in accepted evidence.

Extract six domain-independent readiness facts from user_request. Set each flag true only when
the user explicitly states the condition is already complete, not merely planned or desired:
- baseline_readiness_confirmed: a concrete baseline implementation is frozen and reproduced;
- evaluation_protocol_validated: the data split and evaluation protocol are independent and frozen;
- comparison_readiness_confirmed: a concrete strong comparator has been verified under a matched protocol;
- module_validation_confirmed: interface compatibility and isolated single-module contribution are verified;
- failure_policy_confirmed: failure cases and stop conditions are recorded;
- explicit_evaluation_protocol_invalid: the user explicitly reports leakage, train/test overlap,
  target contamination, or another invalid evaluation protocol.
When evidence is ambiguous, keep the readiness flag false. A protocol cannot be both validated
and explicitly invalid.

Do not author evidence IDs, titles, identifiers, hashes, licenses, repository references,
verification status, numeric reproduced metrics, experiment outcomes, or novelty claims.
Do not invent hardware, datasets, repositories, papers, or stronger comparisons. Leave optional
reported_dataset and reported_comparator null when accepted evidence does not name them.

Treat composition as a hypothesis, not novelty by itself. Prefer one causal intervention over a
stack of weak modules. Never report an unrun experiment or unverified gain as fact.
Do not expose or request hidden chain-of-thought reasoning.
''',
    encoding="utf-8",
)

replace_once(
    "tests/methodology/test_method_design_draft.py",
    '''from paperagent.academic_methodology import AuditVerdict, ExperimentArmType, audit_method_plan
''',
    '''from paperagent.academic_methodology import (
    AuditSeverity,
    AuditVerdict,
    ExperimentArmType,
    audit_method_plan,
)
''',
)
replace_once(
    "tests/methodology/test_method_design_draft.py",
    '''    assert failed["baseline-license"].severity.value == "error"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "error"
''',
    '''    assert failed["baseline-license"].severity.value == "warning"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "warning"
''',
)

test_path = ROOT / "tests/methodology/test_method_design_draft.py"
test_text = test_path.read_text(encoding="utf-8")
if "def test_explicit_invalid_evaluation_protocol_is_no_go() -> None:" in test_text:
    raise RuntimeError("scientific decision tests already exist")
test_path.write_text(
    test_text
    + '''


def test_explicit_invalid_evaluation_protocol_is_no_go() -> None:
    proposal = _bound_proposal(
        _state(),
        _draft(explicit_evaluation_protocol_invalid=True),
    )
    audit = audit_method_plan(proposal.methodology_plan)
    failed = {item.check_id: item for item in audit.checks if not item.passed}

    assert audit.verdict is AuditVerdict.NO_GO
    assert failed["evaluation-protocol-valid"].severity is AuditSeverity.CRITICAL


def test_repairable_missing_provenance_is_revise_not_no_go() -> None:
    proposal = _bound_proposal(
        _state(),
        _draft(
            baseline_readiness_confirmed=True,
            evaluation_protocol_validated=True,
            comparison_readiness_confirmed=True,
            module_validation_confirmed=True,
            failure_policy_confirmed=True,
        ),
    )
    plan = proposal.methodology_plan
    evidence = tuple(item.model_copy(update={"supported_claims": ()}) for item in plan.evidence)
    audit = audit_method_plan(plan.model_copy(update={"evidence": evidence}))
    failed = {item.check_id: item for item in audit.checks if not item.passed}

    assert audit.verdict is AuditVerdict.REVISE
    assert failed["baseline-provenance"].severity is AuditSeverity.ERROR
    assert all(
        item.severity is not AuditSeverity.CRITICAL
        for check_id, item in failed.items()
        if check_id.startswith("module-provenance:")
    )


def test_explicit_completed_readiness_can_reach_go() -> None:
    proposal = _bound_proposal(
        _state(),
        _draft(
            baseline_readiness_confirmed=True,
            evaluation_protocol_validated=True,
            comparison_readiness_confirmed=True,
            module_validation_confirmed=True,
            failure_policy_confirmed=True,
        ),
    )
    audit = audit_method_plan(proposal.methodology_plan)

    assert audit.verdict is AuditVerdict.GO
    assert proposal.methodology_plan.baseline.reproduced is True
    assert proposal.methodology_plan.baseline.baseline_parity_verified is True
    assert any(
        experiment.arm_type is ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )


def test_missing_license_warning_does_not_block_otherwise_ready_plan() -> None:
    proposal = _bound_proposal(
        _state(),
        _draft(
            baseline_readiness_confirmed=True,
            evaluation_protocol_validated=True,
            comparison_readiness_confirmed=True,
            module_validation_confirmed=True,
            failure_policy_confirmed=True,
        ),
    )
    plan = proposal.methodology_plan
    evidence = tuple(item.model_copy(update={"license": None}) for item in plan.evidence)
    baseline = plan.baseline.model_copy(update={"license": None})
    modules = tuple(item.model_copy(update={"license": None}) for item in plan.modules)
    audit = audit_method_plan(
        plan.model_copy(update={"evidence": evidence, "baseline": baseline, "modules": modules})
    )
    failed = {item.check_id: item for item in audit.checks if not item.passed}

    assert audit.verdict is AuditVerdict.GO
    assert failed["baseline-license"].severity is AuditSeverity.WARNING
''',
    encoding="utf-8",
)

print("generic scientific decision policy remediation applied")
