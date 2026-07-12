"""Re8.0 Seeded Research — schema contracts and validators.

Defines the four core data structures introduced by Re8.0:

  - SeedPaperCard        (§5.2) audited user-supplied paper
  - MethodFamilyCard     (§5.3) alternative method route
  - EvidenceGap          (§5.4) motivation for each external search
  - ReasoningLedgerEntry (§5.5) auditable structured decision

All schemas are plain dicts at runtime (LangGraph state friendly); this module
provides constructor + validator helpers so nodes can emit cards without
re-implementing field defaulting / validation, and downstream validators can
reject malformed cards before they enter evidence pools.

Design notes:
  - The constructor never raises on missing fields; it fills defaults so
    nodes can emit partial cards during early phases (e.g. pre-PDF parse).
    Use ``validate_*`` to enforce required fields at gates.
  - existence_status / fulltext_status / role use the enum strings from the
    Re8.0 spec; we keep them as plain strings (no Enum) so JSON
    serialisation stays trivial and LangGraph state diffs stay readable.
  - All card ids are caller-supplied (we do not auto-generate UUIDs here)
    so that fixture-based tests can use deterministic ids.
"""
from __future__ import annotations

from typing import Any

# ── Enum-ish constants (kept as plain strings for JSON friendliness) ────────

ENTRY_MODES = ("topic_only", "seeded_research")
RUN_MODES = ("full_agent", "lite_chain", "offline_replay")
NETWORK_POLICIES = ("online", "cache_first", "offline")
REASONING_POLICIES = ("react_reflection", "chain_only")

SEED_INPUT_FORMS = ("title", "doi", "arxiv", "url", "pdf", "citation")
SEED_EXISTENCE_STATUS = ("verified", "ambiguous", "not_found")
# Re8.0 P1-1: fulltext acquisition three-state progression
#   metadata_only → fulltext_available → fulltext_parsed
# "downloaded" is the legacy value written by paper_understanding (WP2);
# "parse_failed" remains a terminal failure state.
SEED_FULLTEXT_STATUS = (
    "downloaded",        # legacy: paper_understanding parsed a local PDF
    "metadata_only",     # initial: only title/authors/year known
    "parse_failed",      # PDF parse failed
    "fulltext_available",  # P1-1: PDF bytes downloaded, not yet parsed
    "fulltext_parsed",     # P1-1: fulltext parsed into structured fields
)
SEED_ROLES = (
    "classic_anchor",
    "current_sota_candidate",
    "reproduction_target",
    "parallel_inspiration",
    "survey_reference",
    "unknown",
)

METHOD_RELATIONS = (
    "direct_competitor",
    "alternative_formulation",
    "transferable_mechanism",
    "incompatible",
)

GAP_TYPES = (
    "existence",
    "current_baseline",
    "competing_method",
    "mechanism",
    "dataset",
    "repo",
    "environment",
    "counter_evidence",
    "fulltext",  # Re8.0 P1-1: PDF fulltext could not be downloaded (paywall/403/timeout)
)
GAP_STATUS = ("open", "satisfied", "partially_satisfied", "blocked")

LEDGER_STAGES = (
    "seed_audit",
    "family_expansion",
    "search",
    "tailor",
    "review",
    # Re8.0 WP6: Reflection Gate stages — each emits a ledger entry so
    # downstream consumers can audit why a gate passed / triggered
    # re-search / emitted unresolved.
    "seed_audit_gate",
    "tailor_gate",
    "final_review_gate",
)
LEDGER_STATUS = (
    "proposed",
    "evidence_backed",
    "verified",
    "refuted",
    "unresolved",
)

# Re8.0 WP6 §8.7: each Reflection Gate may run at most 2 rounds. After
# the cap is reached the gate must emit ``unresolved`` rather than
# self-loop.
REFLECTION_GATE_MAX_ROUNDS = 2

# Re8.0 WP6 §8.6: tools the Full Agent ReAct loop is allowed to call.
# Any tool outside this whitelist is a hard reject. Lite Chain and
# Offline Replay never reach this list because they short-circuit before
# the ReAct loop is entered.
REACT_TOOL_WHITELIST = (
    "resolve_paper",
    "fetch_metadata",
    "fetch_or_parse_pdf",
    "search_reference_chain",
    "search_method_family",
    "search_repo",
    "search_dataset",
    "extract_reproduction_environment",
    "compile_evidence",
    "request_tailor_review",
)


def make_reflection_gate_result(
    *,
    gate_name: str,
    verdict: str = "unresolved",
    round_idx: int = 0,
    re_search_requests: list[str] | None = None,
    unresolved_gaps: list[str] | None = None,
    rationale: str = "",
    generated_by: str = "llm",
) -> dict[str, Any]:
    """Construct a Reflection Gate result with safe defaults.

    ``verdict`` is one of ``pass`` / ``revise`` / ``unresolved``:
      - pass        → gate is satisfied, no re-search needed
      - revise      → re-search requested; bound to a gap_id; round < cap
      - unresolved  → round cap reached; downstream must accept gaps

    The result is consumed by both the graph router (to decide re-search)
    and the trace_events / ledger fields (for auditability).
    """
    if verdict not in ("pass", "revise", "unresolved"):
        verdict = "unresolved"
    return {
        "gate_name": gate_name,
        "verdict": verdict,
        "round_idx": int(round_idx),
        "re_search_requests": list(re_search_requests or []),
        "unresolved_gaps": list(unresolved_gaps or []),
        "rationale": rationale,
        "generated_by": generated_by,
    }


def validate_reflection_gate_result(result: dict[str, Any]) -> list[str]:
    """Return validation errors for a Reflection Gate result (empty = valid)."""
    errs: list[str] = []
    if not result.get("gate_name"):
        errs.append("gate_name is required")
    if result.get("verdict") not in ("pass", "revise", "unresolved"):
        errs.append("verdict must be one of (pass, revise, unresolved)")
    if not isinstance(result.get("round_idx"), int):
        errs.append("round_idx must be int")
    if not isinstance(result.get("re_search_requests"), list):
        errs.append("re_search_requests must be list")
    if not isinstance(result.get("unresolved_gaps"), list):
        errs.append("unresolved_gaps must be list")
    return errs


# ── SeedPaperCard ───────────────────────────────────────────────────────────

def make_seed_card(
    *,
    seed_id: str,
    input_form: str = "title",
    resolved_title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    canonical_url: str | None = None,
    existence_status: str = "ambiguous",
    fulltext_status: str = "metadata_only",
    role: str = "unknown",
    task_definition: str | None = None,
    method_summary: str | None = None,
    dataset_and_metrics: dict[str, Any] | None = None,
    reproduction_environment: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    raw_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a SeedPaperCard with sensible defaults.

    Nodes should call this instead of building the dict inline so that we
    can evolve the schema in one place.
    """
    return {
        "seed_id": seed_id,
        "input_form": input_form,
        "resolved_title": resolved_title,
        "authors": list(authors or []),
        "year": year,
        "doi": doi,
        "canonical_url": canonical_url,
        "existence_status": existence_status,
        "fulltext_status": fulltext_status,
        "role": role,
        "task_definition": task_definition,
        "method_summary": method_summary,
        "dataset_and_metrics": dict(dataset_and_metrics or {}),
        "reproduction_environment": dict(reproduction_environment or {}),
        "limitations": list(limitations or []),
        "evidence_ids": list(evidence_ids or []),
        "raw_input": dict(raw_input or {}),
    }


def validate_seed_card(card: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid).

    A card with ``existence_status="verified"`` is the only kind allowed to
    enter ``verified_papers``. ``ambiguous`` / ``not_found`` cards stay in
    ``seed_cards`` for downstream reasoning but never become evidence.
    """
    errs: list[str] = []
    if not card.get("seed_id"):
        errs.append("seed_id is required")
    if card.get("input_form") not in SEED_INPUT_FORMS:
        errs.append(f"input_form must be one of {SEED_INPUT_FORMS}")
    if card.get("existence_status") not in SEED_EXISTENCE_STATUS:
        errs.append(f"existence_status must be one of {SEED_EXISTENCE_STATUS}")
    if card.get("fulltext_status") not in SEED_FULLTEXT_STATUS:
        errs.append(f"fulltext_status must be one of {SEED_FULLTEXT_STATUS}")
    if card.get("role") not in SEED_ROLES:
        errs.append(f"role must be one of {SEED_ROLES}")
    # Verified cards must carry enough identity to be citeable
    if card.get("existence_status") == "verified":
        if not (card.get("resolved_title") or card.get("doi") or card.get("canonical_url")):
            errs.append(
                "verified seed must have at least one of resolved_title / doi / canonical_url"
            )
    return errs


def is_seed_evidence_eligible(card: dict[str, Any]) -> bool:
    """True iff the card may enter verified_papers as evidence.

    Re8.0 §6.2: only ``verified`` cards with at least one stable identifier
    (title or DOI or canonical URL) are eligible. ``ambiguous`` cards are
    retained for reasoning but never become evidence.
    """
    return (
        card.get("existence_status") == "verified"
        and bool(card.get("resolved_title") or card.get("doi") or card.get("canonical_url"))
        and not validate_seed_card(card)
    )


# ── MethodFamilyCard ────────────────────────────────────────────────────────

def make_method_family(
    *,
    family_id: str,
    name: str,
    task_type: str = "other",
    relation_to_seed: str = "alternative_formulation",
    applicability_conditions: list[str] | None = None,
    interface_requirements: list[str] | None = None,
    expected_strengths: list[str] | None = None,
    expected_weaknesses: list[str] | None = None,
    search_queries: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "name": name,
        "task_type": task_type,
        "relation_to_seed": relation_to_seed,
        "applicability_conditions": list(applicability_conditions or []),
        "interface_requirements": list(interface_requirements or []),
        "expected_strengths": list(expected_strengths or []),
        "expected_weaknesses": list(expected_weaknesses or []),
        "search_queries": list(search_queries or []),
    }


def validate_method_family(card: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not card.get("family_id"):
        errs.append("family_id is required")
    if not card.get("name"):
        errs.append("name is required")
    if card.get("relation_to_seed") not in METHOD_RELATIONS:
        errs.append(f"relation_to_seed must be one of {METHOD_RELATIONS}")
    return errs


# ── EvidenceGap ─────────────────────────────────────────────────────────────

def make_evidence_gap(
    *,
    gap_id: str,
    question: str,
    gap_type: str = "existence",
    why_needed: str = "",
    related_claim_ids: list[str] | None = None,
    success_condition: str = "",
    budget: dict[str, Any] | None = None,
    status: str = "open",
) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "question": question,
        "gap_type": gap_type,
        "why_needed": why_needed,
        "related_claim_ids": list(related_claim_ids or []),
        "success_condition": success_condition,
        "budget": dict(budget or {}),
        "status": status,
    }


def validate_evidence_gap(gap: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not gap.get("gap_id"):
        errs.append("gap_id is required")
    if not gap.get("question"):
        errs.append("question is required")
    if gap.get("gap_type") not in GAP_TYPES:
        errs.append(f"gap_type must be one of {GAP_TYPES}")
    if gap.get("status") not in GAP_STATUS:
        errs.append(f"status must be one of {GAP_STATUS}")
    return errs


# ── ReasoningLedgerEntry ────────────────────────────────────────────────────

def make_ledger_entry(
    *,
    decision_id: str,
    stage: str,
    decision: str,
    evidence_ids: list[str] | None = None,
    alternatives_considered: list[str] | None = None,
    rejection_reasons: list[str] | None = None,
    hypothesis: str | None = None,
    falsifier: str | None = None,
    next_action: str = "",
    confidence: float = 0.0,
    status: str = "proposed",
) -> dict[str, Any]:
    # Clamp confidence to [0, 1]
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        c = 0.0
    if c < 0.0:
        c = 0.0
    elif c > 1.0:
        c = 1.0
    return {
        "decision_id": decision_id,
        "stage": stage,
        "decision": decision,
        "evidence_ids": list(evidence_ids or []),
        "alternatives_considered": list(alternatives_considered or []),
        "rejection_reasons": list(rejection_reasons or []),
        "hypothesis": hypothesis,
        "falsifier": falsifier,
        "next_action": next_action,
        "confidence": c,
        "status": status,
    }


def validate_ledger_entry(entry: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not entry.get("decision_id"):
        errs.append("decision_id is required")
    if entry.get("stage") not in LEDGER_STAGES:
        errs.append(f"stage must be one of {LEDGER_STAGES}")
    if not entry.get("decision"):
        errs.append("decision is required")
    if entry.get("status") not in LEDGER_STATUS:
        errs.append(f"status must be one of {LEDGER_STATUS}")
    if not isinstance(entry.get("confidence"), (int, float)):
        errs.append("confidence must be a number")
    return errs


# ── Entry / run mode defaults ───────────────────────────────────────────────

def default_re80_state(
    *,
    entry_mode: str = "topic_only",
    run_mode: str = "lite_chain",
    network_policy: str = "online",
    reasoning_policy: str = "chain_only",
) -> dict[str, Any]:
    """Return the Re8.0 policy fields with safe defaults.

    Used by intake_node to seed state when caller did not specify a mode.
    Defaults are conservative (lite_chain + chain_only) so that existing
    topic_only callers get unchanged behavior.
    """
    if entry_mode not in ENTRY_MODES:
        entry_mode = "topic_only"
    if run_mode not in RUN_MODES:
        run_mode = "lite_chain"
    if network_policy not in NETWORK_POLICIES:
        network_policy = "online"
    if reasoning_policy not in REASONING_POLICIES:
        reasoning_policy = "chain_only"
    return {
        "entry_mode": entry_mode,
        "run_mode": run_mode,
        "network_policy": network_policy,
        "reasoning_policy": reasoning_policy,
        "seed_cards": [],
        "candidate_seeds": [],
        "method_families": [],
        "evidence_gaps": [],
        "reasoning_ledger": [],
        "search_budget": {
            "max_queries": 20,
            "max_papers": 30,
            "max_wall_time_minutes": 20,
        },
    }
