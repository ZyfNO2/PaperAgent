from __future__ import annotations

from pydantic import Field

from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace, EvidenceReview
from paperagent.claw_benchmark_adapter import (
    BenchmarkNormalizationContext as LegacyNormalizationContext,
)
from paperagent.claw_benchmark_adapter import normalize_paperagent_state as _legacy_normalize
from paperagent.schemas.base import FrozenModel
from paperagent.state import PaperAgentState


class BenchmarkNormalizationContext(FrozenModel):
    """Explicit, gold-independent normalization inputs.

    Decision routing and leakage flags are required structured inputs. The normalizer never
    infers them from free-text actions, clarification wording, fixture labels, or case text.
    """

    case_id: str = Field(min_length=1)
    resolved_unknowns: tuple[str, ...] = ()
    pilot_recommended: bool = False
    asked_user_to_design_method: bool = False
    full_text_evidence_ids: tuple[str, ...] = ()
    stronger_baselines_considered: bool | None = None
    negative_results_visible: bool | None = None
    future_or_test_leakage: bool = False
    leakage_findings: tuple[str, ...] = ()


def _ledger_grounded_reviews(
    state: PaperAgentState,
    reviews: tuple[EvidenceReview, ...],
) -> tuple[EvidenceReview, ...]:
    """Use the canonical Evidence Ledger as the normalization source of truth.

    The ledger is produced by the production verification path and already records identity,
    relevance scope, accepted gap bindings, claims, and the final acceptance decision. This
    function does not upgrade rejected evidence or infer facts from titles or free text.
    """

    ledger = state.get("evidence_ledger")
    if ledger is None:
        return reviews
    entries = {entry.evidence_id: entry for entry in ledger.entries}
    normalized: list[EvidenceReview] = []
    for review in reviews:
        entry = entries.get(review.evidence_id)
        if entry is None:
            normalized.append(review)
            continue
        accepted_supports = tuple(
            support for support in entry.gap_supports if support.decision == "accept"
        )
        gap_ids = tuple(dict.fromkeys(support.gap_id for support in accepted_supports))
        role = review.role
        if role is None and accepted_supports:
            role = "gap"
        relevance_passed = entry.relevance_scope in {"direct", "indirect"}
        normalized.append(
            review.model_copy(
                update={
                    "identity_verified": entry.identity_verified,
                    "relevance_reviewed": True,
                    "relevance_passed": relevance_passed,
                    "accepted": entry.accepted,
                    "role": role,
                    "gap_ids": gap_ids or review.gap_ids,
                    "claim_ids": tuple(entry.supported_claims) or review.claim_ids,
                    "core_evidence": role in {"baseline", "gap", "parallel_method"},
                }
            )
        )
    return tuple(normalized)


def normalize_paperagent_state(
    state: PaperAgentState,
    context: BenchmarkNormalizationContext,
) -> AcademicTailoringRunTrace:
    """Normalize state while disabling all text-derived benchmark label inference."""

    trace = _legacy_normalize(
        state,
        LegacyNormalizationContext(
            case_id=context.case_id,
            resolved_unknowns=context.resolved_unknowns,
            pilot_recommended=context.pilot_recommended,
            asked_user_to_design_method=context.asked_user_to_design_method,
            full_text_evidence_ids=context.full_text_evidence_ids,
            stronger_baselines_considered=context.stronger_baselines_considered,
            negative_results_visible=context.negative_results_visible,
        ),
    )
    error_codes = tuple(trace.trace_error_codes)
    if context.leakage_findings:
        error_codes = tuple(dict.fromkeys((*error_codes, *context.leakage_findings)))
    return trace.model_copy(
        update={
            "evidence_reviews": _ledger_grounded_reviews(state, trace.evidence_reviews),
            "pilot_recommended": context.pilot_recommended,
            "future_or_test_leakage": context.future_or_test_leakage,
            "trace_error_codes": error_codes,
        }
    )


__all__ = ["BenchmarkNormalizationContext", "normalize_paperagent_state"]
