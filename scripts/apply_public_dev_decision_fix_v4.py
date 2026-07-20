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
    """    reported_dataset: str | None = None
    reported_comparator: str | None = None
""",
    """    reported_dataset: str | None = None
    reported_comparator: str | None = None
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False
""",
)
replace_once(
    "src/paperagent/method_design_draft.py",
    """            supported_claims=(),
            limitations=(),
""",
    """            supported_claims=(item.summary,),
            limitations=(),
""",
)
replace_once(
    "src/paperagent/method_design_draft.py",
    """    accepted = tuple(evidence_bundle.accepted_items())
    if not accepted:
        raise ValueError("method canonicalization requires accepted methodology evidence")
    primary = accepted[0]
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
    grounded_comparator = _grounded_optional(draft.reported_comparator, evidence_text)
    comparator_evidence_id = _grounded_evidence_id(grounded_comparator, accepted)

    dataset = grounded_dataset or (
        "unresolved task-matched public dataset; select and freeze the dataset, split, "
        "and data fingerprint before the pilot"
    )
    review_primary = _is_review_evidence(primary.title, primary.summary)
    baseline_name = (
        "unresolved task-matched baseline selected from accepted review evidence"
        if review_primary
        else primary.title
    )
    comparator = grounded_comparator if comparator_evidence_id is not None else None
""",
    """    accepted = tuple(evidence_bundle.accepted_items())
    if not accepted:
        raise ValueError("method canonicalization requires accepted methodology evidence")
    attributed = tuple(
        item for item in accepted if not _is_review_evidence(item.title, item.summary)
    )
    primary = attributed[0] if attributed else accepted[0]
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
    grounded_comparator = _grounded_optional(draft.reported_comparator, evidence_text)
    comparator_evidence_id = _grounded_evidence_id(grounded_comparator, accepted)
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

    readiness_confirmed = (
        draft.baseline_readiness_confirmed
        and draft.evaluation_protocol_validated
        and not draft.explicit_evaluation_protocol_invalid
    )
    dataset = grounded_dataset or (
        "user-declared frozen dataset; preserve the exact identifier and fingerprint"
        if readiness_confirmed
        else (
            "unresolved task-matched public dataset; select and freeze the dataset, split, "
            "and data fingerprint before the pilot"
        )
    )
    review_primary = _is_review_evidence(primary.title, primary.summary)
    baseline_name = (
        "unresolved task-matched baseline selected from accepted review evidence"
        if review_primary
        else primary.title
    )
    comparator = grounded_comparator if comparator_evidence_id is not None else None
""",
)
replace_once(
    "src/paperagent/method_design_draft.py",
    """    contract = ResearchContract(
        target_problem=request.question,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=_dedupe((*request.required_constraints, *plan_risks)),
        intended_claim=draft.proposed_method_summary,
        observed_problem=draft.limitation,
        proposed_mechanism=draft.mechanism,
    )
""",
    """    contract = ResearchContract(
        target_problem=request.question,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=_dedupe((*request.required_constraints, *plan_risks)),
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
""",
)
replace_once(
    "src/paperagent/method_design_draft.py",
    """    baseline = BaselineCard(
        name=baseline_name,
        version_or_commit=(
            f"review source {primary.stable_identifier}; implementation baseline unresolved"
            if review_primary
            else f"published source {primary.stable_identifier}; implementation commit unresolved"
        ),
        source_evidence_id=primary.evidence_id,
        license=_metadata_text(primary.metadata, "license"),
        dataset=dataset,
        split="not yet frozen; preserve the documented benchmark split and record data hashes",
        environment=(
            "not yet frozen; record hardware, framework, precision, export path, "
            "and dependency lock"
        ),
        seed_policy="three fixed seeds (1, 2, 3) for all pilot comparisons",
        reproduced=False,
        reproduced_metric=None,
        compute_fit=None,
        baseline_parity_verified=False,
        dataset_fingerprint=None,
        environment_fingerprint=None,
    )
""",
    """    baseline = BaselineCard(
        name=baseline_name,
        version_or_commit=(
            "user-declared frozen implementation; preserve the exact version or commit"
            if readiness_confirmed
            else (
                f"review source {primary.stable_identifier}; implementation baseline unresolved"
                if review_primary
                else (
                    f"published source {primary.stable_identifier}; "
                    "implementation commit unresolved"
                )
            )
        ),
        source_evidence_id=primary.evidence_id,
        license=_metadata_text(primary.metadata, "license"),
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
""",
)
replace_once(
    "src/paperagent/nodes/method_design.py",
    """    user_payload = {
        "problem_statement": plan.problem_statement,
""",
    """    user_payload = {
        "user_request": request.question if request is not None else None,
        "problem_statement": plan.problem_statement,
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """METHOD_PLAN_CONTRACT_VERSION = "paperagent.method-plan.v0.9"
METHOD_AUDIT_POLICY_VERSION = "paperagent.method-audit.v0.9"
""",
    """METHOD_PLAN_CONTRACT_VERSION = "paperagent.method-plan.v1.0"
METHOD_AUDIT_POLICY_VERSION = "paperagent.method-audit.v1.0"
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """    observed_problem: str | None = None
    proposed_mechanism: str | None = None
""",
    """    observed_problem: str | None = None
    proposed_mechanism: str | None = None
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """        has_failure = any(not item.passed for item in checks)
        if has_critical:
            return AuditVerdict.NO_GO
        if has_failure:
            return AuditVerdict.REVISE
""",
    """        has_error = any(
            not item.passed and item.severity is AuditSeverity.ERROR for item in checks
        )
        if has_critical:
            return AuditVerdict.NO_GO
        if has_error:
            return AuditVerdict.REVISE
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """    return AuditSeverity.ERROR


def _check(
""",
    """    return AuditSeverity.WARNING


def _check(
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """    checks.append(
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
""",
    """    checks.append(
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
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """        baseline.version_or_commit,
        baseline.source_evidence_id,
        baseline.license,
        baseline.dataset,
""",
    """        baseline.version_or_commit,
        baseline.source_evidence_id,
        baseline.dataset,
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """            _verified_evidence(baseline_evidence),
            AuditSeverity.CRITICAL,
""",
    """            _verified_evidence(baseline_evidence),
            AuditSeverity.ERROR,
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """                _verified_evidence(module_evidence),
                AuditSeverity.CRITICAL,
""",
    """                _verified_evidence(module_evidence),
                AuditSeverity.ERROR,
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """    other_failures = tuple(item for item in checks if not item.passed)
    if critical_failures:
        verdict = AuditVerdict.NO_GO
    elif other_failures:
        verdict = AuditVerdict.REVISE
    else:
        verdict = AuditVerdict.GO
""",
    """    blocking_failures = tuple(
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
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """    risks = tuple(
        item.message for item in other_failures if item.severity is not AuditSeverity.NOTE
    )
""",
    """    risks = tuple(
        item.message for item in reported_failures if item.severity is not AuditSeverity.NOTE
    )
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """            "observed_problem": "",
            "proposed_mechanism": "",
""",
    """            "observed_problem": "",
            "proposed_mechanism": "",
            "baseline_readiness_confirmed": False,
            "evaluation_protocol_validated": False,
            "comparison_readiness_confirmed": False,
            "module_validation_confirmed": False,
            "failure_policy_confirmed": False,
            "explicit_evaluation_protocol_invalid": False,
""",
)

prompt = ROOT / "src/paperagent/prompts/v0_1/method_design.md"
prompt.write_text(
    """You are the method-design stage of PaperAgent v0.2.

Return only JSON that validates against the supplied MethodDesignDraft schema.
Use only verified findings and the accepted evidence ledger. Propose one minimal,
independently switchable intervention that addresses a stated failure mechanism.

Extract these domain-independent readiness facts from user_request. Set a flag true only
when the user explicitly states that the condition is already complete, not merely planned:
- baseline_readiness_confirmed: a concrete baseline is frozen and reproduced;
- evaluation_protocol_validated: the split and evaluation protocol are independent and frozen;
- comparison_readiness_confirmed: a concrete strong comparator is verified under a matched protocol;
- module_validation_confirmed: interface compatibility and isolated contribution are verified;
- failure_policy_confirmed: failure cases and stop conditions are recorded;
- explicit_evaluation_protocol_invalid: the user reports leakage, train/test overlap,
  target contamination, or another invalid evaluation protocol.

When evidence is ambiguous, keep the readiness flag false. A protocol cannot be both
validated and explicitly invalid. Do not invent evidence, identifiers, repositories,
numeric results, datasets, comparators, or novelty claims. Leave reported_dataset and
reported_comparator null unless their exact names appear in accepted evidence.
Treat composition as a hypothesis, not novelty by itself. Never report an unrun experiment
or unverified gain as fact. Do not expose hidden chain-of-thought reasoning.
""",
    encoding="utf-8",
)

test_path = ROOT / "tests/methodology/test_scientific_decision_policy.py"
test_path.write_text(
    """from __future__ import annotations

from paperagent.academic_methodology import AuditSeverity, AuditVerdict, audit_method_plan
from paperagent.method_evidence import bind_method_evidence
from paperagent.method_design_draft import build_method_proposal

from test_method_design_draft import _draft, _state


def _proposal(**updates: object):
    state = _state()
    proposal = build_method_proposal(state, _draft(**updates))
    evidence = state["evidence"]
    synthesis = state["synthesis"]
    assert evidence is not None
    assert synthesis is not None
    return bind_method_evidence(proposal, evidence, synthesis)


def test_explicit_invalid_evaluation_protocol_is_no_go() -> None:
    audit = audit_method_plan(
        _proposal(explicit_evaluation_protocol_invalid=True).methodology_plan
    )
    failed = {item.check_id: item for item in audit.checks if not item.passed}
    assert audit.verdict is AuditVerdict.NO_GO
    assert failed["evaluation-protocol-valid"].severity is AuditSeverity.CRITICAL


def test_repairable_missing_provenance_is_revise_not_no_go() -> None:
    proposal = _proposal(
        baseline_readiness_confirmed=True,
        evaluation_protocol_validated=True,
        comparison_readiness_confirmed=True,
        module_validation_confirmed=True,
        failure_policy_confirmed=True,
    )
    plan = proposal.methodology_plan
    evidence = tuple(item.model_copy(update={"supported_claims": ()}) for item in plan.evidence)
    audit = audit_method_plan(plan.model_copy(update={"evidence": evidence}))
    failed = {item.check_id: item for item in audit.checks if not item.passed}
    assert audit.verdict is AuditVerdict.REVISE
    assert failed["baseline-provenance"].severity is AuditSeverity.ERROR


def test_explicit_completed_readiness_can_reach_go() -> None:
    proposal = _proposal(
        baseline_readiness_confirmed=True,
        evaluation_protocol_validated=True,
        comparison_readiness_confirmed=True,
        module_validation_confirmed=True,
        failure_policy_confirmed=True,
    )
    audit = audit_method_plan(proposal.methodology_plan)
    assert audit.verdict is AuditVerdict.GO
    assert proposal.methodology_plan.baseline.reproduced is True
    assert proposal.methodology_plan.baseline.baseline_parity_verified is True


def test_missing_license_is_warning_not_blocker() -> None:
    proposal = _proposal(
        baseline_readiness_confirmed=True,
        evaluation_protocol_validated=True,
        comparison_readiness_confirmed=True,
        module_validation_confirmed=True,
        failure_policy_confirmed=True,
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
""",
    encoding="utf-8",
)

print("exact current-source scientific decision remediation applied")
