from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paperagent.academic_tailoring import TailoringDecision, compose_tailored_research_proposal
from paperagent.academic_tailoring_evaluation import (
    AcademicTailoringCaseSpec,
    grade_proposal,
    load_case_specs,
    materialize_task,
)
from paperagent.academic_tailoring_fixtures import load_tailoring_task_bundle
from paperagent.rag_evaluation import (
    ClaimAssessment,
    RAGEvaluationInput,
    RAGEvaluationReport,
    RetrievedEvidence,
    evaluate_rag_case,
)

GOLD_CASE_ID = "npc-go-complete"
GOLD_CASE_CONTRACT_VERSION = "paperagent.gold-case.v2"
GOLD_CASE_REQUIRED_CHECKS = frozenset(
    {
        "expected_go_decision",
        "canonical_audit_go",
        "rubric_passed",
        "minimum_score_met",
        "complete_recall_at_5",
        "all_claims_citation_supported",
        "no_unsupported_claims",
        "no_critical_unsupported_claims",
        "synthetic_scope_declared",
        "scientific_release_not_claimed",
    }
)


def _report_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class GoldCaseReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    status: Literal["passed", "failed"]
    scientific_claim: Literal["not_claimed"]
    proposal_decision: str = Field(min_length=1)
    audit_verdict: str = Field(min_length=1)
    grade_score: int = Field(ge=0, le=100)
    minimum_score: int = Field(ge=0, le=100)
    grade_passed: bool
    plan_fingerprint: str = Field(min_length=1)
    proposal_fingerprint: str = Field(min_length=1)
    evidence_scope: str = Field(min_length=1)
    readiness: str = Field(min_length=1)
    scientific_release_ready: bool
    rag: RAGEvaluationReport
    acceptance_checks: dict[str, bool]
    limitations: tuple[str, ...]
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_integrity(self) -> GoldCaseReport:
        if self.contract_version != GOLD_CASE_CONTRACT_VERSION:
            raise ValueError("unsupported Gold Case contract version")
        if self.case_id != GOLD_CASE_ID:
            raise ValueError("unexpected Gold Case identifier")
        if set(self.acceptance_checks) != GOLD_CASE_REQUIRED_CHECKS:
            raise ValueError("Gold Case acceptance check set is incomplete or unknown")
        if not self.limitations or any(not item.strip() for item in self.limitations):
            raise ValueError("Gold Case limitations must be non-empty and non-blank")

        derived_checks = {
            "expected_go_decision": self.proposal_decision == "GO",
            "canonical_audit_go": self.audit_verdict == "GO",
            "rubric_passed": self.grade_passed,
            "minimum_score_met": self.grade_score >= self.minimum_score,
            "complete_recall_at_5": self.rag.recall_at_k.get("5") == 1.0,
            "all_claims_citation_supported": self.rag.citation_support_rate == 1.0,
            "no_unsupported_claims": self.rag.unsupported_claim_rate == 0.0,
            "no_critical_unsupported_claims": not self.rag.critical_unsupported_claims,
            "synthetic_scope_declared": self.evidence_scope == "synthetic_evaluation",
            "scientific_release_not_claimed": not self.scientific_release_ready,
        }
        if self.acceptance_checks != derived_checks:
            raise ValueError("Gold Case acceptance checks diverge from report fields")

        expected_status = "passed" if all(derived_checks.values()) else "failed"
        if self.status != expected_status:
            raise ValueError("Gold Case status diverges from acceptance checks")

        payload = self.model_dump(mode="json", exclude={"report_digest"})
        expected_digest = _report_digest(payload)
        if not hmac.compare_digest(self.report_digest, expected_digest):
            raise ValueError("Gold Case report digest mismatch")
        return self


def _select_gold_spec(
    specs: tuple[AcademicTailoringCaseSpec, ...],
) -> AcademicTailoringCaseSpec:
    matches = tuple(spec for spec in specs if spec.case_id == GOLD_CASE_ID)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {GOLD_CASE_ID!r} case, found {len(matches)}")
    return matches[0]


def _build_rag_input(task_root: Path) -> RAGEvaluationInput:
    task = load_tailoring_task_bundle(task_root)
    retrieved = tuple(
        RetrievedEvidence(
            evidence_id=paper.paper_id,
            stable_identifier=paper.stable_identifier,
            rank=index,
            context_tokens=128,
            cited=True,
        )
        for index, paper in enumerate(task.papers, start=1)
    )
    # Baseline reproduction is server-owned execution metadata. It is evaluated by the
    # canonical methodology audit and must not be represented as supported merely by
    # citing the baseline paper.
    claims: list[ClaimAssessment] = [
        ClaimAssessment(
            claim_id=f"module-{intent.source_paper_id}",
            supporting_evidence_ids=(intent.source_paper_id,),
            critical=True,
        )
        for intent in task.module_intents
    ]
    claims.extend(
        ClaimAssessment(
            claim_id=f"comparison-{comparison.name}",
            supporting_evidence_ids=(comparison.source_paper_id,),
            critical=False,
        )
        for comparison in task.strong_comparisons
    )
    used_tokens = sum(item.context_tokens for item in retrieved)
    return RAGEvaluationInput(
        case_id=GOLD_CASE_ID,
        relevant_identifiers=tuple(paper.stable_identifier for paper in task.papers),
        retrieved=retrieved,
        claims=tuple(claims),
        total_context_tokens=used_tokens,
        used_context_tokens=used_tokens,
        llm_calls=0,
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=0.0,
        terminal="succeeded",
    )


def run_gold_case(repository_root: Path) -> GoldCaseReport:
    fixture_root = repository_root / "evals" / "academic_tailoring" / "npc"
    task = load_tailoring_task_bundle(fixture_root)
    spec = _select_gold_spec(
        load_case_specs(repository_root / "evals" / "academic_tailoring" / "cases.json")
    )
    materialized = materialize_task(task, spec.mutation)
    proposal = compose_tailored_research_proposal(materialized)
    grade = grade_proposal(spec, materialized, proposal)
    rag = evaluate_rag_case(_build_rag_input(fixture_root), cutoffs=(1, 3, 5))

    checks = {
        "expected_go_decision": proposal.decision is TailoringDecision.GO,
        "canonical_audit_go": proposal.audit_verdict.value == "GO",
        "rubric_passed": grade.passed,
        "minimum_score_met": grade.score >= spec.minimum_score,
        "complete_recall_at_5": rag.recall_at_k["5"] == 1.0,
        "all_claims_citation_supported": rag.citation_support_rate == 1.0,
        "no_unsupported_claims": rag.unsupported_claim_rate == 0.0,
        "no_critical_unsupported_claims": not rag.critical_unsupported_claims,
        "synthetic_scope_declared": proposal.evidence_scope.value == "synthetic_evaluation",
        "scientific_release_not_claimed": not proposal.scientific_release_ready,
    }
    status: Literal["passed", "failed"] = "passed" if all(checks.values()) else "failed"
    payload: dict[str, object] = {
        "contract_version": GOLD_CASE_CONTRACT_VERSION,
        "case_id": GOLD_CASE_ID,
        "status": status,
        "scientific_claim": "not_claimed",
        "proposal_decision": proposal.decision.value,
        "audit_verdict": proposal.audit_verdict.value,
        "grade_score": grade.score,
        "minimum_score": spec.minimum_score,
        "grade_passed": grade.passed,
        "plan_fingerprint": proposal.plan_fingerprint,
        "proposal_fingerprint": proposal.proposal_fingerprint,
        "evidence_scope": proposal.evidence_scope.value,
        "readiness": proposal.readiness.value,
        "scientific_release_ready": proposal.scientific_release_ready,
        "rag": rag.model_dump(mode="json"),
        "acceptance_checks": checks,
        "limitations": (
            "All evidence records are synthetic fixtures used for deterministic "
            "engineering evaluation.",
            "No real paper, dataset, baseline training run, or empirical result is "
            "reproduced here.",
            "The report proves contract convergence and evaluability, not scientific "
            "novelty or quality.",
        ),
    }
    return GoldCaseReport.model_validate(
        {
            **payload,
            "report_digest": _report_digest(payload),
        }
    )