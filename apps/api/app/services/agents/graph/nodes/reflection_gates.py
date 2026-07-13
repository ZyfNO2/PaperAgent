"""Re8.0 WP6 — Reflection Gates + ReAct tool whitelist + Ledger enforcement.

Implements the three Reflection Gates from Plan §8.7:

  1. ``seed_audit_gate``  — after SeedResolver: are seeds real, role-correct,
     and information-sufficient?
  2. ``tailor_gate``      — after TailorSkillAdapter: are modules compatible,
     is there a simpler route, can the experiment falsify the claim?
  3. ``final_review_gate`` — after NoveltyReview: does the narrative exceed
     evidence, is there highly similar work, do we need extra evidence?

Each gate:
  - Short-circuits to ``pass`` when ``run_mode != "full_agent"`` or
    ``reasoning_policy != "react_reflection"`` (Plan §8.5 capability matrix).
  - Caps at ``REFLECTION_GATE_MAX_ROUNDS`` (default 2). After the cap the
    gate emits ``unresolved`` and refuses to self-loop (Plan §8.7).
  - Writes a ``ReasoningLedgerEntry`` so downstream consumers can audit
    why a gate passed / triggered re-search / emitted unresolved.
  - Emits a ``trace_events`` entry with provider/verdict/generated_by for
    parity with the WP5 trace symmetry contract.

ReAct tool whitelist (Plan §8.6) is enforced via ``REACT_TOOL_WHITELIST``
in ``re80_schema``. ``is_tool_allowed`` is the single chokepoint —
search_agent and any future ReAct dispatcher MUST consult it before
dispatching a tool call. Lite Chain / Offline Replay never reach the
whitelist because they short-circuit before the ReAct loop is entered.

Schema stability: ``_normalize_gate_output`` is the single chokepoint
that converts any LLM shape (well-behaved / sloppy / minimal) into the
fixed gate_result schema, mirroring the WP5 _normalize_tailor_output /
normalize_review_output pattern.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.re80_schema import (
    LEDGER_STAGES,
    REACT_TOOL_WHITELIST,
    REFLECTION_GATE_MAX_ROUNDS,
    make_ledger_entry,
    make_reflection_gate_result,
    validate_ledger_entry,
    validate_reflection_gate_result,
)
from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)

# ── Gate names (single source of truth) ─────────────────────────────────────

GATE_SEED_AUDIT = "seed_audit_gate"
GATE_TAILOR = "tailor_gate"
GATE_FINAL_REVIEW = "final_review_gate"

_GATE_NAMES = (GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW)

# Allowed gate verdicts (subset of make_reflection_gate_result contract)
GATE_VERDICTS = ("pass", "revise", "unresolved")


# ── Mode / policy short-circuit ─────────────────────────────────────────────


def is_react_reflection_enabled(state: ResearchState) -> bool:
    """True iff the current run may invoke ReAct/Reflection.

    Plan §8.5 capability matrix:
      - Full Agent        → ReAct bounded, Reflection ≤ 2 rounds
      - Lite Chain        → ReAct off, Reflection off
      - Offline Replay    → ReAct off, Reflection off, network off

    Both conditions must hold: ``run_mode == "full_agent"`` AND
    ``reasoning_policy == "react_reflection"``. Either missing → off.
    """
    return (
        state.get("run_mode") == "full_agent"
        and state.get("reasoning_policy") == "react_reflection"
    )


# ── ReAct tool whitelist enforcement ────────────────────────────────────────


def is_tool_allowed(tool_name: str) -> bool:
    """Single chokepoint for ReAct tool whitelist (Plan §8.6).

    Any tool outside ``REACT_TOOL_WHITELIST`` is a hard reject. Lite
    Chain and Offline Replay never reach this check because they short-
    circuit before the ReAct loop is entered.
    """
    return tool_name in REACT_TOOL_WHITELIST


# ── Gate round tracking ────────────────────────────────────────────────────


def _get_gate_rounds(state: ResearchState, gate_name: str) -> int:
    """Return the number of rounds already executed for ``gate_name``."""
    results = state.get("reflection_gate_results") or {}
    return len(results.get(gate_name, []))


def _append_gate_result(
    state: ResearchState,
    gate_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build the state patch that appends ``result`` to the gate's log.

    Returns the new ``reflection_gate_results`` dict (full replacement
    so LangGraph merges it cleanly without needing a custom reducer).
    """
    existing = dict(state.get("reflection_gate_results") or {})
    gate_log = list(existing.get(gate_name, []))
    gate_log.append(result)
    existing[gate_name] = gate_log
    return existing


# ── Schema enforcement (chokepoint for model-switch stability) ──────────────


def _clamp_verdict(raw: Any) -> str:
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in GATE_VERDICTS:
            return v
        if "pass" in v or "ok" in v or "accept" in v:
            return "pass"
        if "revise" in v or "repair" in v or "search" in v:
            return "revise"
        if "unresolved" in v or "fail" in v or "stop" in v:
            return "unresolved"
    return "unresolved"  # conservative default — never silently downgrade


def _ensure_str_list(raw: Any, max_items: int = 10) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw[:max_items] if x is not None]


def _normalize_gate_output(
    raw: dict[str, Any] | None,
    *,
    gate_name: str,
    round_idx: int,
    generated_by: str = "llm",
) -> dict[str, Any]:
    """Force any LLM shape into the fixed gate_result schema.

    This is the WP6 mirror of WP5's _normalize_tailor_output /
    normalize_review_output: regardless of which model produced ``raw``,
    the output always carries the same 7 keys so downstream consumers
    don't need to special-case per model.
    """
    raw = raw if isinstance(raw, dict) else {}
    rationale_raw = raw.get("rationale")
    if rationale_raw is None or (isinstance(rationale_raw, str) and not rationale_raw.strip()):
        rationale = "no rationale provided"
    else:
        rationale = str(rationale_raw)
    result = make_reflection_gate_result(
        gate_name=gate_name,
        verdict=_clamp_verdict(raw.get("verdict")),
        round_idx=round_idx,
        re_search_requests=_ensure_str_list(raw.get("re_search_requests")),
        unresolved_gaps=_ensure_str_list(raw.get("unresolved_gaps")),
        rationale=rationale,
        generated_by=raw.get("generated_by", generated_by),
    )
    # Sanity check — never let a malformed gate result escape
    errs = validate_reflection_gate_result(result)
    if errs:
        logger.warning(
            "reflection_gate %s produced invalid result %r: %s",
            gate_name, result, errs,
        )
        # Fall back to unresolved — never silently drop
        result = make_reflection_gate_result(
            gate_name=gate_name,
            verdict="unresolved",
            round_idx=round_idx,
            rationale=f"normalization failed: {errs}",
            generated_by=generated_by,
        )
    return result


# ── Rule-based gate fallbacks (LLM unavailable / offline test mode) ─────────
#
# Each gate has a deterministic rule layer that fires when:
#   * LLM call raises
#   * LLM returns malformed JSON
#   * entry_mode != "seeded_research" (no seed cards to evaluate)
#
# The rule layer reads only fields already in state — it cannot
# hallucinate evidence. It always emits a conservative verdict.


def _rule_seed_audit_gate(state: ResearchState) -> dict[str, Any]:
    """Conservative rule-based Seed Audit Gate evaluation.

    Pass iff at least one verified seed card exists with a non-unknown
    role. Otherwise → revise (request re-search for the seed identity).
    """
    seed_cards = state.get("seed_cards") or []
    verified = [c for c in seed_cards
                if c.get("existence_status") == "verified"]
    if not verified:
        return {
            "verdict": "revise",
            "re_search_requests": ["resolve_seed_identity"],
            "rationale": "no verified seed card found",
        }
    role_unknown = [c for c in verified if c.get("role") == "unknown"]
    if role_unknown:
        return {
            "verdict": "revise",
            "re_search_requests": ["classify_seed_role"],
            "rationale": f"{len(role_unknown)} verified seed(s) have role=unknown",
        }
    return {
        "verdict": "pass",
        "rationale": f"{len(verified)} verified seed(s) with assigned roles",
    }


def _rule_tailor_gate(state: ResearchState) -> dict[str, Any]:
    """Conservative rule-based Tailor Gate evaluation.

    Pass iff tailored_method carries verdict in {GO, REVISE} and
    ablation_matrix has ≥4 rows (Baseline / A / B / A+B per Plan §9.1).
    """
    tailored = state.get("tailored_method") or {}
    if not tailored:
        return {
            "verdict": "revise",
            "re_search_requests": ["request_tailor_review"],
            "rationale": "tailored_method absent — request tailor re-run",
        }
    verdict = (tailored.get("verdict") or "").upper()
    if verdict == "NO-GO":
        return {
            "verdict": "unresolved",
            "rationale": "tailor returned NO-GO; no further re-search can help",
        }
    ablation = tailored.get("ablation_matrix") or []
    if len(ablation) < 4:
        return {
            "verdict": "revise",
            "re_search_requests": ["search_method_family"],
            "rationale": f"ablation_matrix has {len(ablation)} rows, need ≥4",
        }
    return {
        "verdict": "pass",
        "rationale": f"tailor verdict={verdict}, ablation rows={len(ablation)}",
    }


def _rule_final_review_gate(state: ResearchState) -> dict[str, Any]:
    """Conservative rule-based Final Review Gate evaluation.

    Pass iff novelty_review_verdict is ``accepted`` AND
    falsifiable_hypothesis is non-empty. Otherwise → revise / unresolved.
    """
    verdict = (state.get("novelty_review_verdict") or "").lower()
    hypothesis = state.get("falsifiable_hypothesis") or ""
    if verdict == "accepted" and hypothesis and hypothesis != "unspecified":
        return {
            "verdict": "pass",
            "rationale": f"review accepted with falsifiable hypothesis",
        }
    if verdict == "weak_reject":
        return {
            "verdict": "revise",
            "re_search_requests": ["search_method_family", "search_dataset"],
            "rationale": "weak_reject — request targeted re-search",
        }
    if verdict == "reject":
        return {
            "verdict": "unresolved",
            "rationale": "review rejected; no further re-search can rescue",
        }
    return {
        "verdict": "revise",
        "re_search_requests": ["compile_evidence"],
        "rationale": f"review verdict={verdict or 'missing'}, hypothesis empty={not hypothesis}",
    }


_RULE_FALLBACKS = {
    GATE_SEED_AUDIT: _rule_seed_audit_gate,
    GATE_TAILOR: _rule_tailor_gate,
    GATE_FINAL_REVIEW: _rule_final_review_gate,
}


# ── Ledger entry construction ───────────────────────────────────────────────


def _make_gate_ledger(
    *,
    gate_name: str,
    decision_id: str,
    result: dict[str, Any],
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a ReasoningLedgerEntry for a Reflection Gate decision."""
    verdict = result.get("verdict", "unresolved")
    # Map gate verdict → ledger status
    # (pass → verified, revise → proposed, unresolved → unresolved)
    status_map = {
        "pass": "verified",
        "revise": "proposed",
        "unresolved": "unresolved",
    }
    entry = make_ledger_entry(
        decision_id=decision_id,
        stage=gate_name,  # in LEDGER_STAGES since WP6
        decision=f"gate_verdict={verdict}",
        evidence_ids=evidence_ids or [],
        alternatives_considered=result.get("re_search_requests", []),
        rejection_reasons=[] if verdict == "pass" else [result.get("rationale", "")],
        hypothesis=None,
        falsifier=None,
        next_action="continue" if verdict == "pass" else (
            "re_search" if verdict == "revise" else "stop"
        ),
        confidence=1.0 if verdict == "pass" else (0.5 if verdict == "revise" else 0.0),
        status=status_map.get(verdict, "unresolved"),
    )
    errs = validate_ledger_entry(entry)
    if errs:
        logger.warning("reflection_gate %s produced invalid ledger: %s", gate_name, errs)
    return entry


# ── Gate prompt builders (LLM path) ─────────────────────────────────────────


_GATE_SYSTEM = (
    "You are a research Reflection Gate. Evaluate the current pipeline "
    "state and decide whether the gate passes, needs revision (targeted "
    "re-search), or is unresolved (cap reached / hard failure). "
    "Every criticism MUST cite a gap_id or evidence_id from the input. "
    "Output ONLY valid JSON."
)

_SEED_AUDIT_PROMPT = """Reflection Gate: Seed Audit (Plan §8.7 #1)

Evaluate whether the seed cards are real, role-correct, and information-
sufficient for downstream method-family exploration.

Seed cards:
{seed_cards_json}

Evidence gaps currently open:
{evidence_gaps_json}

Decide:
- pass       — at least one verified seed with non-unknown role
- revise     — re-search requested to resolve seed identity / role
- unresolved — cap reached, cannot repair seeds

Output JSON:
{{
  "verdict": "pass" | "revise" | "unresolved",
  "re_search_requests": ["gap_id_1", "gap_id_2"],
  "unresolved_gaps": ["gap_id_3"],
  "rationale": "one-sentence justification citing gap_id / seed_id"
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


_TAILOR_PROMPT = """Reflection Gate: Tailor (Plan §8.7 #2)

Evaluate whether the tailored method is compatible, falsifiable, and
whether a simpler route exists.

Tailored method:
{tailored_json}

Open evidence gaps:
{evidence_gaps_json}

Note on method specification:
- The method description lives in `assembly_plan.description` (there is
  no top-level `core_method` field in the tailored_method schema).
- If `assembly_plan.description` is non-empty, treat it as the method
  specification — do NOT reject on missing method details.
- If `assembly_plan.description` is empty, `revise` is appropriate
  (insufficient method specification).

Decide:
- pass       — verdict in {{GO, REVISE}}, ablation ≥4 rows, gaps addressable
- revise     — request re-search for missing modules / baselines
- unresolved — verdict=NO-GO or cap reached

Output JSON:
{{
  "verdict": "pass" | "revise" | "unresolved",
  "re_search_requests": ["gap_id_1"],
  "unresolved_gaps": ["gap_id_2"],
  "rationale": "one-sentence justification"
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


_FINAL_REVIEW_PROMPT = """Reflection Gate: Final Review (Plan §8.7 #3)

Evaluate whether the narrative exceeds evidence, whether highly similar
work exists, and whether extra evidence is needed.

Novelty review verdict: {review_verdict}
Falsifiable hypothesis: {falsifiable_hypothesis}
Contribution type: {contribution_type}
Pressure points: {pressure_points_json}
Open evidence gaps: {evidence_gaps_json}

Decide:
- pass       — accepted, hypothesis non-empty, no critical pressure point
- revise     — request targeted re-search to address pressure point
- unresolved — reject or cap reached

Output JSON:
{{
  "verdict": "pass" | "revise" | "unresolved",
  "re_search_requests": ["gap_id_1"],
  "unresolved_gaps": ["gap_id_2"],
  "rationale": "one-sentence justification"
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


def _build_seed_audit_prompt(state: ResearchState) -> str:
    import json as _json
    seed_cards = state.get("seed_cards") or []
    gaps = state.get("evidence_gaps") or []
    return _SEED_AUDIT_PROMPT.format(
        seed_cards_json=_json.dumps(seed_cards[:5], ensure_ascii=False, default=str)[:3000],
        evidence_gaps_json=_json.dumps(
            [{"gap_id": g.get("gap_id", ""), "question": g.get("question", "")} for g in gaps[:10]],
            ensure_ascii=False, default=str,
        )[:2000],
    )


def _build_tailor_prompt(state: ResearchState) -> str:
    import json as _json
    tailored = state.get("tailored_method") or {}
    gaps = state.get("evidence_gaps") or []
    return _TAILOR_PROMPT.format(
        tailored_json=_json.dumps(tailored, ensure_ascii=False, default=str)[:3000],
        evidence_gaps_json=_json.dumps(
            [{"gap_id": g.get("gap_id", ""), "question": g.get("question", "")} for g in gaps[:10]],
            ensure_ascii=False, default=str,
        )[:2000],
    )


def _build_final_review_prompt(state: ResearchState) -> str:
    import json as _json
    pressure_points = state.get("pressure_points") or []
    gaps = state.get("evidence_gaps") or []
    return _FINAL_REVIEW_PROMPT.format(
        review_verdict=state.get("novelty_review_verdict", "unknown"),
        falsifiable_hypothesis=state.get("falsifiable_hypothesis", "") or "unspecified",
        contribution_type=state.get("contribution_type", "unknown"),
        pressure_points_json=_json.dumps(pressure_points[:5], ensure_ascii=False, default=str)[:2000],
        evidence_gaps_json=_json.dumps(
            [{"gap_id": g.get("gap_id", ""), "question": g.get("question", "")} for g in gaps[:10]],
            ensure_ascii=False, default=str,
        )[:2000],
    )


_GATE_PROMPT_BUILDERS = {
    GATE_SEED_AUDIT: _build_seed_audit_prompt,
    GATE_TAILOR: _build_tailor_prompt,
    GATE_FINAL_REVIEW: _build_final_review_prompt,
}


# ── Common gate runner ─────────────────────────────────────────────────────


def _run_gate(
    state: ResearchState,
    *,
    gate_name: str,
    profile: str = "premium_review",
    contract_id: str = "reflection-gate/v1",
) -> dict[str, Any]:
    """Run a Reflection Gate.

    Flow:
      1. Short-circuit when Lite/Offline (emit pass + trace, no LLM call).
      2. Round-cap check — if already at REFLECTION_GATE_MAX_ROUNDS+,
         emit unresolved + trace, do not self-loop.
      3. LLM evaluation via call_json_with_validation.
      4. On LLM failure / non-dict / exception → rule fallback
         (generated_by="fallback", never silently drop).
      5. Normalize via _normalize_gate_output (schema stability).
      6. Write ReasoningLedgerEntry + trace_events + reflection_gate_results.

    Returns a state patch dict.
    """
    t0 = time.time()
    round_idx = _get_gate_rounds(state, gate_name)

    # ── 1. Mode short-circuit ──────────────────────────────────────────────
    if not is_react_reflection_enabled(state):
        result = make_reflection_gate_result(
            gate_name=gate_name,
            verdict="pass",
            round_idx=round_idx,
            rationale=(
                f"short-circuit: run_mode={state.get('run_mode', 'missing')}, "
                f"reasoning_policy={state.get('reasoning_policy', 'missing')}"
            ),
            generated_by="skip",
        )
        trace = _emit(
            f"reflection_gate::{gate_name}", t0,
            {"run_mode": state.get("run_mode"), "round_idx": round_idx,
             "activated": False},
            {"verdict": "pass", "generated_by": "skip"},
            [], "n/a", [],
            state_keys=["reflection_gate_results", "reasoning_ledger", "trace_events"],
        )
        ledger = _make_gate_ledger(
            gate_name=gate_name,
            decision_id=f"{gate_name}-skip-r{round_idx}",
            result=result,
        )
        return {
            "reflection_gate_results": _append_gate_result(state, gate_name, result),
            "reasoning_ledger": [ledger],
            "trace_events": [trace],
        }

    # ── 2. Round-cap check ────────────────────────────────────────────────
    if round_idx >= REFLECTION_GATE_MAX_ROUNDS:
        result = make_reflection_gate_result(
            gate_name=gate_name,
            verdict="unresolved",
            round_idx=round_idx,
            rationale=f"cap reached: {round_idx}/{REFLECTION_GATE_MAX_ROUNDS}",
            generated_by="rule",
        )
        trace = _emit(
            f"reflection_gate::{gate_name}", t0,
            {"round_idx": round_idx, "cap": REFLECTION_GATE_MAX_ROUNDS,
             "activated": True},
            {"verdict": "unresolved", "generated_by": "rule"},
            [], "n/a", [],
            state_keys=["reflection_gate_results", "reasoning_ledger", "trace_events"],
        )
        ledger = _make_gate_ledger(
            gate_name=gate_name,
            decision_id=f"{gate_name}-cap-r{round_idx}",
            result=result,
        )
        return {
            "reflection_gate_results": _append_gate_result(state, gate_name, result),
            "reasoning_ledger": [ledger],
            "trace_events": [trace],
        }

    # ── 3. LLM evaluation ─────────────────────────────────────────────────
    prompt_builder = _GATE_PROMPT_BUILDERS[gate_name]
    prompt = prompt_builder(state)
    prov = profile

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system=_GATE_SYSTEM,
            node_name=gate_name,
            profile=profile,
            contract_id=contract_id,
            max_tokens=800,
            timeout=30.0,
            fallback=None,  # we want to know if LLM failed; rule fallback below
        )
        if isinstance(raw, dict):
            result = _normalize_gate_output(
                raw, gate_name=gate_name, round_idx=round_idx,
                generated_by="llm",
            )
        else:
            # LLM returned non-dict or None — use rule fallback
            rule_out = _RULE_FALLBACKS[gate_name](state)
            result = _normalize_gate_output(
                rule_out, gate_name=gate_name, round_idx=round_idx,
                generated_by="fallback",
            )
            prov = "fallback"
    except Exception as exc:
        logger.warning("reflection_gate %s LLM call failed: %s — using rule fallback",
                       gate_name, exc)
        rule_out = _RULE_FALLBACKS[gate_name](state)
        result = _normalize_gate_output(
            rule_out, gate_name=gate_name, round_idx=round_idx,
            generated_by="fallback",
        )
        prov = "fallback"

    # ── 4. Emit trace + ledger + state patch ──────────────────────────────
    trace = _emit(
        f"reflection_gate::{gate_name}", t0,
        {"round_idx": round_idx, "activated": True,
         "entry_mode": state.get("entry_mode")},
        {"verdict": result["verdict"], "generated_by": result["generated_by"],
         "re_search_requests": result["re_search_requests"]},
        [], prov, [],
        state_keys=["reflection_gate_results", "reasoning_ledger", "trace_events"],
    )
    ledger = _make_gate_ledger(
        gate_name=gate_name,
        decision_id=f"{gate_name}-r{round_idx}",
        result=result,
    )
    return {
        "reflection_gate_results": _append_gate_result(state, gate_name, result),
        "reasoning_ledger": [ledger],
        "trace_events": [trace],
    }


# ── Public LangGraph node wrappers ─────────────────────────────────────────


def seed_audit_gate_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: Seed Audit Reflection Gate (Plan §8.7 #1)."""
    return _run_gate(state, gate_name=GATE_SEED_AUDIT)


def tailor_gate_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: Tailor Reflection Gate (Plan §8.7 #2)."""
    return _run_gate(state, gate_name=GATE_TAILOR)


def final_review_gate_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: Final Review Reflection Gate (Plan §8.7 #3)."""
    return _run_gate(state, gate_name=GATE_FINAL_REVIEW)


# ── Conditional repair routing (Plan §8.7 close-the-loop) ──────────────────
#
# Re8.0 P0-2: when a gate emits ``verdict=revise`` and the round cap has
# not been reached, the graph must route BACK to the upstream node that
# can fix the gap (seed_resolver / search_planner / evidence_context).
# When the gate passes, is unresolved, or has hit the round cap, the
# graph continues forward to the next node in the linear spine.

_GATE_FORWARD_TARGETS = {
    # Re8.0 post-audit: fulltext_acquisition now runs before
    # paper_understanding so DOI/arXiv seeds get their PDFs downloaded
    # first. The gate must forward to fulltext_acquisition (the new
    # first node in the understanding spine), not paper_understanding.
    GATE_SEED_AUDIT: "fulltext_acquisition",
    GATE_TAILOR: "innovation_extractor",
    GATE_FINAL_REVIEW: "falsifiability",
}

_GATE_REPAIR_TARGETS = {
    GATE_SEED_AUDIT: "seed_resolver",
    GATE_TAILOR: "search_planner",
    GATE_FINAL_REVIEW: "evidence_context",
}

# Re8.0 P1-1: Repair-path gate dependencies.
# When a gate emits verdict=revise and routes to its repair target, the
# repair path may re-trigger a DIFFERENT gate that has already hit its
# round cap. Continuing to route into such a path produces an ineffective
# loop: the downstream gate immediately re-emits unresolved (cap reached),
# the graph routes forward, and we are back where we started — but with
# inflated round_idx values on the downstream gate (observed: tailor_gate
# round_idx=4 when MAX_ROUNDS=2).
#
# Mapping: gate → list of OTHER gates whose cap status must be checked
# before allowing repair routing. If any listed gate is already capped
# (last verdict == unresolved OR round_idx >= MAX_ROUNDS), the current
# gate forwards instead of repairing, because the repair path cannot
# produce new signal.
_GATE_REPAIR_PATH_DOWNSTREAM_GATES = {
    GATE_FINAL_REVIEW: [GATE_TAILOR],  # evidence_context → tailor_skill_adapter → tailor_gate
}


def _is_gate_capped(state: ResearchState, gate_name: str) -> bool:
    """Return True if ``gate_name`` has hit its round cap or is unresolved.

    A gate is "capped" when its last logged verdict is ``unresolved`` or
    its round_idx has reached ``REFLECTION_GATE_MAX_ROUNDS``. In either
    case, re-entering the gate's repair path cannot produce new signal —
    the gate will immediately re-emit unresolved.
    """
    results = (state.get("reflection_gate_results") or {}).get(gate_name, [])
    if not results:
        return False
    last = results[-1]
    verdict = last.get("verdict", "unresolved")
    try:
        round_idx = int(last.get("round_idx", 0))
    except (TypeError, ValueError):
        round_idx = 0
    return verdict == "unresolved" or round_idx >= REFLECTION_GATE_MAX_ROUNDS


def route_after_gate(state: ResearchState, gate_name: str) -> str:
    """Return the next node name after a Reflection Gate.

    Used by ``graph.add_conditional_edges`` to wire the close-the-loop
    repair routing (Re8.0 P0-2). The returned string MUST be a key in
    the conditional-edge mapping dict in ``research_graph.py``.

    Decision table (Plan §8.7):

      verdict=pass        → forward target (gate satisfied)
      verdict=unresolved  → forward target (cap reached / hard failure;
                            downstream must accept open gaps)
      verdict=revise + round_idx < MAX_ROUNDS → repair target
      verdict=revise + round_idx >= MAX_ROUNDS → forward target
                            (defensive: gate normally emits unresolved
                            at the cap, but guard against any path that
                            leaks a revise past the cap)

    Repair targets:
        - seed_audit_gate   → ``seed_resolver`` (re-resolve seeds)
        - tailor_gate       → ``search_planner`` (targeted re-search)
        - final_review_gate → ``evidence_context`` (compile more evidence)

    Forward targets:
        - seed_audit_gate   → ``fulltext_acquisition`` (Re8.0 post-audit:
          was paper_understanding, but fulltext_acquisition now runs first
          so PDFs are downloaded before paper_understanding parses them)
        - tailor_gate       → ``innovation_extractor``
        - final_review_gate → ``falsifiability``

    Raises:
        ValueError: if ``gate_name`` is not one of the 3 known gates.
        This is a programming error (the graph only wires 3 gates), so
        we fail fast rather than silently route to a wrong node.
    """
    forward = _GATE_FORWARD_TARGETS.get(gate_name)
    repair = _GATE_REPAIR_TARGETS.get(gate_name)
    if forward is None or repair is None:
        raise ValueError(
            f"route_after_gate: unknown gate_name={gate_name!r}; "
            f"expected one of {_GATE_NAMES}"
        )

    # Read the gate's last result. The gate node always runs before this
    # router, so the log should be non-empty; we defend against an empty
    # log by routing forward (no signal to act on).
    results = (state.get("reflection_gate_results") or {}).get(gate_name, [])
    if not results:
        logger.debug(
            "route_after_gate: no result logged for %s — routing forward to %s",
            gate_name, forward,
        )
        return forward

    last = results[-1]
    verdict = last.get("verdict", "unresolved")
    try:
        round_idx = int(last.get("round_idx", 0))
    except (TypeError, ValueError):
        round_idx = 0

    # Cap reached OR pass OR unresolved → forward
    if (
        verdict == "pass"
        or verdict == "unresolved"
        or round_idx >= REFLECTION_GATE_MAX_ROUNDS
    ):
        return forward

    # verdict == "revise" and under cap → would normally repair.
    # Re8.0 P1-1: but if the repair path re-triggers a downstream gate
    # that is already capped, repairing is futile — the downstream gate
    # will immediately re-emit unresolved and we will loop back here with
    # inflated round_idx on the downstream gate. Forward instead.
    downstream_gates = _GATE_REPAIR_PATH_DOWNSTREAM_GATES.get(gate_name, [])
    for dg in downstream_gates:
        if _is_gate_capped(state, dg):
            logger.info(
                "route_after_gate: %s verdict=revise but downstream gate "
                "%s is capped (unresolved/round cap reached) — forwarding "
                "to %s to avoid ineffective repair loop",
                gate_name, dg, forward,
            )
            return forward

    # verdict == "revise" and under cap → repair
    return repair


__all__ = [
    # Constants
    "GATE_SEED_AUDIT",
    "GATE_TAILOR",
    "GATE_FINAL_REVIEW",
    "GATE_VERDICTS",
    # Helpers
    "is_react_reflection_enabled",
    "is_tool_allowed",
    "_normalize_gate_output",
    "_clamp_verdict",
    "_get_gate_rounds",
    "_make_gate_ledger",
    # Routing
    "route_after_gate",
    # Nodes
    "seed_audit_gate_node",
    "tailor_gate_node",
    "final_review_gate_node",
]
