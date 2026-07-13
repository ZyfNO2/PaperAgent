"""Re8.0 WP5 — Academic Tailor Skill Adapter.

Compiles structured Skill input from seeded_research state (SeedPaperCard,
MethodFamilyCard, Search Lanes, Evidence Gaps, verified papers, baselines)
and produces a TailoredMethodCard with the 8 required fields from
``Plan/...Re8.0...md`` §9.1:

1. primary_baseline + selection_reason
2. candidate_modules + source evidence
3. compatibility_analysis (semantic / interface / training objective)
4. assembly_plan (minimum viable stitching)
5. ablation_matrix (Baseline / A / B / A+B at minimum)
6. fair_comparison_requirements
7. verdict ∈ {GO, REVISE, NO-GO}
8. evidence_gaps_for_research (directed re-search requests)

Activation gate: only fires for ``entry_mode == "seeded_research"``.
For ``topic_only`` the node returns an empty patch so the existing
``optimization_advisor`` / ``narrative_builder`` chain is untouched.

Schema stability: the LLM output is normalized through ``_normalize_tailor_output``
which fills missing fields and clamps ``verdict`` to the allowed set, so
switching models never breaks downstream consumers. On total failure a
rule-based fallback is returned with ``generated_by="fallback"``.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


# ── Schema constants ───────────────────────────────────────────────────────

TAILOR_VERDICTS = ("GO", "REVISE", "NO-GO")
COMPATIBILITY_LEVELS = ("compatible", "partial", "incompatible")
CONTRIBUTION_FALLBACK = "engineering"

_TAILOR_SYSTEM = (
    "You are the Academic Tailor. Given structured baseline / module / "
    "evidence context, design a minimum-viable method assembly with an "
    "ablation matrix and a GO/REVISE/NO-GO verdict. "
    "Output ONLY valid JSON."
)

_TAILOR_PROMPT_TEMPLATE = """Design a tailored research method for the seeded input.

Topic: {topic}

Seed Papers (verified):
{seed_context}

Method Families:
{family_context}

Search Lanes (with gap bindings):
{lane_context}

Open Evidence Gaps:
{gap_context}

Baselines (from classifier):
{baseline_context}

Innovation Points:
{innovation_context}

User Constraints:
{constraints_context}

---

Produce ALL of the following fields. Every claim MUST cite an evidence_id
from the context above; if no evidence exists, mark the field as "proposed"
rather than inventing a citation.

1. primary_baseline: {{"baseline_id": "...", "title": "...", "selection_reason": "..."}}
2. candidate_modules: [{{"module_id": "...", "name": "...", "source_evidence_id": "...", "target_failure_mode": "..."}}]
3. compatibility_analysis: [{{"module_id": "...", "semantic": "compatible|partial|incompatible", "interface": "...", "training_objective": "...", "notes": "..."}}]
4. assembly_plan: {{"description": "...", "steps": ["..."], "expected_interfaces": ["..."]}}
5. ablation_matrix: [{{"experiment_id": "baseline|A|B|A+B", "config": "...", "tests_hypothesis": "...", "expected_signal": "..."}}]  — at least Baseline / A / B / A+B
6. fair_comparison_requirements: ["..."]
7. verdict: "GO" | "REVISE" | "NO-GO"
8. verdict_reason: "..."
9. evidence_gaps_for_research: [{{"gap_id": "...", "description": "...", "priority": "high|medium|low"}}]

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


# ── Input compilation ─────────────────────────────────────────────────────


def _format_seed_context(seed_cards: list[dict[str, Any]]) -> str:
    if not seed_cards:
        return "(no seed papers)"
    parts: list[str] = []
    for c in seed_cards[:6]:
        role = c.get("role", "unknown")
        title = c.get("resolved_title") or c.get("raw_input", {}).get("title") or "(untitled)"
        task = c.get("task_definition") or ""
        method = c.get("method_summary") or ""
        dataset = c.get("dataset_and_metrics") or {}
        env = c.get("reproduction_environment") or {}
        limitations = c.get("limitations") or []
        parts.append(
            f"[{c.get('seed_id', '?')}] role={role} | {title}\n"
            f"  task: {task[:200]}\n  method: {method[:200]}\n"
            f"  dataset: {json.dumps(dataset, ensure_ascii=False)[:200]}\n"
            f"  environment: {json.dumps(env, ensure_ascii=False)[:200]}\n"
            f"  limitations: {', '.join(str(l) for l in limitations[:3])[:200]}"
        )
    return "\n".join(parts)


def _format_family_context(families: list[dict[str, Any]]) -> str:
    if not families:
        return "(no method families)"
    parts: list[str] = []
    for f in families[:4]:
        parts.append(
            f"[{f.get('family_id', '?')}] {f.get('name', '')} "
            f"— relation: {f.get('relation_to_seed', 'unknown')}"
        )
    return "\n".join(parts)


def _format_lane_context(lanes: list[dict[str, Any]]) -> str:
    if not lanes:
        return "(no search lanes)"
    parts: list[str] = []
    for lane in lanes[:5]:
        gap_id = lane.get("gap_id") or "(unbound)"
        queries = lane.get("queries") or []
        qstr = "; ".join(queries[:2])
        parts.append(
            f"[{lane.get('lane_id', '?')}] gap={gap_id} | {qstr[:120]}"
        )
    return "\n".join(parts)


def _format_gap_context(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return "(no open gaps)"
    parts: list[str] = []
    for g in gaps[:8]:
        parts.append(
            f"[{g.get('gap_id', '?')}] type={g.get('gap_type', '?')} "
            f"status={g.get('status', '?')} | {g.get('question', '')[:120]}"
        )
    return "\n".join(parts)


def _format_baseline_context(baselines: list[dict[str, Any]]) -> str:
    if not baselines:
        return "(no baselines classified yet)"
    parts: list[str] = []
    for b in baselines[:5]:
        parts.append(
            f"[{b.get('id') or b.get('candidate_id', '?')}] {b.get('title', '')}"
        )
    return "\n".join(parts)


def _format_innovation_context(innovations: list[dict[str, Any]]) -> str:
    if not innovations:
        return "(no innovation points extracted yet)"
    parts: list[str] = []
    for i in innovations[:5]:
        parts.append(f"- {str(i.get('point', i))[:160]}")
    return "\n".join(parts)


def _format_constraints(state: dict[str, Any]) -> str:
    budget = state.get("search_budget") or {}
    return json.dumps(
        {
            "run_mode": state.get("run_mode", "full_agent"),
            "network_policy": state.get("network_policy", "online"),
            "budget": budget,
        },
        ensure_ascii=False,
    )


def build_tailor_prompt(state: ResearchState) -> str:
    """Compile structured Skill input from seeded_research state."""
    return _TAILOR_PROMPT_TEMPLATE.format(
        topic=(state.get("topic") or "")[:200],
        seed_context=_format_seed_context(state.get("seed_cards") or []),
        family_context=_format_family_context(state.get("method_families") or []),
        lane_context=_format_lane_context(state.get("search_lanes") or []),
        gap_context=_format_gap_context(state.get("evidence_gaps") or []),
        baseline_context=_format_baseline_context(state.get("baseline_candidates") or []),
        innovation_context=_format_innovation_context(state.get("innovation_points") or []),
        constraints_context=_format_constraints(state),
    )


# ── Output normalization / schema enforcement ─────────────────────────────


def _clamp_verdict(raw: Any) -> str:
    if isinstance(raw, str):
        v = raw.strip().upper()
        if v in TAILOR_VERDICTS:
            return v
        # Common drift: "accept" / "go" without caps
        if "go" in v and "no" not in v:
            return "GO"
        if "revise" in v:
            return "REVISE"
        if "no" in v:
            return "NO-GO"
    return "REVISE"  # safest middle verdict when unknown


def _clamp_compatibility(raw: Any) -> str:
    if isinstance(raw, str):
        c = raw.strip().lower()
        if c in COMPATIBILITY_LEVELS:
            return c
    return "partial"


def _ensure_list(raw: Any, max_items: int = 20) -> list[Any]:
    if isinstance(raw, list):
        return raw[:max_items]
    return []


def _normalize_tailor_output(raw: dict[str, Any]) -> dict[str, Any]:
    """Enforce Tailor schema regardless of which model produced ``raw``.

    This is the single chokepoint that guarantees schema stability across
    model switches (WP5 acceptance: "切换至少三类模型时 Schema 稳定").
    """
    primary = raw.get("primary_baseline")
    if not isinstance(primary, dict):
        primary = {
            "baseline_id": "",
            "title": str(primary) if primary else "",
            "selection_reason": "",
        }

    modules = _ensure_list(raw.get("candidate_modules"))
    for m in modules:
        if not isinstance(m, dict):
            continue
        m.setdefault("module_id", "")
        m.setdefault("name", "")
        m.setdefault("source_evidence_id", "")
        m.setdefault("target_failure_mode", "")

    compat = _ensure_list(raw.get("compatibility_analysis"))
    for c in compat:
        if not isinstance(c, dict):
            continue
        c["semantic"] = _clamp_compatibility(c.get("semantic"))
        c.setdefault("interface", "")
        c.setdefault("training_objective", "")
        c.setdefault("notes", "")

    assembly = raw.get("assembly_plan")
    if not isinstance(assembly, dict):
        assembly = {"description": str(assembly) if assembly else "",
                    "steps": [], "expected_interfaces": []}
    assembly.setdefault("steps", [])
    assembly.setdefault("expected_interfaces", [])

    ablation = _ensure_list(raw.get("ablation_matrix"))
    # Guarantee at least Baseline / A / B / A+B rows exist (§11.2 methodology gate)
    existing_ids = {str(a.get("experiment_id", "")).lower()
                    for a in ablation if isinstance(a, dict)}
    for required in ("baseline", "a", "b", "a+b"):
        if required not in existing_ids:
            ablation.append({
                "experiment_id": required,
                "config": "",
                "tests_hypothesis": "",
                "expected_signal": "",
            })

    fair_reqs = _ensure_list(raw.get("fair_comparison_requirements"))
    fair_reqs = [str(r) for r in fair_reqs if r is not None]

    verdict = _clamp_verdict(raw.get("verdict"))
    verdict_reason = str(raw.get("verdict_reason", ""))

    gaps = _ensure_list(raw.get("evidence_gaps_for_research"))
    for g in gaps:
        if not isinstance(g, dict):
            continue
        g.setdefault("gap_id", "")
        g.setdefault("description", "")
        prio = str(g.get("priority", "medium")).lower()
        g["priority"] = prio if prio in ("high", "medium", "low") else "medium"

    # Re8.0 third batch: ensure assembly_plan.description is non-empty so
    # Tailor Gate LLM does not reject on "insufficient method specification".
    # If LLM returned empty description, derive a fallback from
    # candidate_modules / primary_baseline / ablation_matrix.
    # Note: ablation_matrix is always backfilled to >=4 rows by the logic
    # above, so it cannot be used to distinguish "LLM provided ablation" from
    # "template only". Prioritise modules and primary_baseline title instead.
    if not (assembly.get("description") or "").strip():
        module_names = [
            m.get("name", "") for m in modules
            if isinstance(m, dict) and (m.get("name") or "").strip()
        ]
        if module_names:
            assembly["description"] = (
                f"assembly plan: combine modules ({', '.join(module_names[:3])})"
            )
        else:
            primary_title = (primary.get("title") or "").strip() if isinstance(primary, dict) else ""
            if primary_title:
                assembly["description"] = f"assembly plan: derived from {primary_title}"
            else:
                assembly["description"] = "assembly plan: see ablation_matrix for experiment config"

    return {
        "primary_baseline": primary,
        "candidate_modules": modules,
        "compatibility_analysis": compat,
        "assembly_plan": assembly,
        "ablation_matrix": ablation,
        "fair_comparison_requirements": fair_reqs,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "evidence_gaps_for_research": gaps,
        "generated_by": raw.get("generated_by", "llm"),
    }


# ── Rule-based fallback (§9.3 step 3) ─────────────────────────────────────


def _fallback_tailor(state: ResearchState) -> dict[str, Any]:
    """Rule-based Tailor output when LLM unavailable or output unusable.

    Marks ``generated_by="fallback"`` so downstream Claim Judge knows not
    to treat strong claims as evidence-backed.
    """
    baselines = state.get("baseline_candidates") or []
    b0 = baselines[0] if baselines else {}
    seed_cards = state.get("seed_cards") or []
    seed_title = ""
    if seed_cards:
        seed_title = (seed_cards[0].get("resolved_title")
                      or seed_cards[0].get("raw_input", {}).get("title", "")
                      or "")
    gaps = state.get("evidence_gaps") or []
    gap_request = [
        {"gap_id": g.get("gap_id", ""), "description": g.get("question", ""),
         "priority": "high" if g.get("status") == "open" else "medium"}
        for g in gaps[:4] if g.get("status") in ("open", "partially_satisfied")
    ]
    return {
        "primary_baseline": {
            "baseline_id": str(b0.get("id") or b0.get("candidate_id", "")),
            "title": str(b0.get("title", seed_title or "unknown baseline")),
            "selection_reason": "fallback: first available baseline (no LLM reasoning)",
        },
        "candidate_modules": [],
        "compatibility_analysis": [],
        "assembly_plan": {
            "description": "fallback: no assembly designed (LLM unavailable)",
            "steps": [],
            "expected_interfaces": [],
        },
        "ablation_matrix": [
            {"experiment_id": "baseline", "config": "reproduce primary baseline",
             "tests_hypothesis": "sanity", "expected_signal": "matches reported metric"},
            {"experiment_id": "a", "config": "add module A",
             "tests_hypothesis": "module A addresses failure mode",
             "expected_signal": "improvement on target metric"},
            {"experiment_id": "b", "config": "add module B",
             "tests_hypothesis": "module B addresses failure mode",
             "expected_signal": "improvement on target metric"},
            {"experiment_id": "a+b", "config": "combine A and B",
             "tests_hypothesis": "additive or synergistic effect",
             "expected_signal": ">= max(A, B)"},
        ],
        "fair_comparison_requirements": [
            "same dataset splits", "same evaluation protocol",
            "same compute budget (or noted)",
        ],
        "verdict": "REVISE",
        "verdict_reason": "fallback: insufficient LLM analysis to issue GO",
        "evidence_gaps_for_research": gap_request,
        "generated_by": "fallback",
    }


# ── Node entry ────────────────────────────────────────────────────────────


def tailor_skill_adapter_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: run the Academic Tailor Skill.

    Activation gate: only fires for ``entry_mode == "seeded_research"``.
    For ``topic_only`` returns an empty patch (existing optimization_advisor
    / narrative_builder chain handles that path).

    Flow (per §9.3 Skill Adapter):
      1. compile structured input
      2. call LLM via call_json_with_validation (profile=premium_review)
      3. normalize through _normalize_tailor_output (schema stability)
      4. on failure → rule fallback with generated_by="fallback"
      5. emit trace with provider / generated_by / verdict
      6. append ReasoningLedgerEntry (stage="tailor")
    """
    t0 = time.time()
    entry_mode = state.get("entry_mode", "topic_only")

    # Gate: only seeded_research activates the Tailor Skill.
    if entry_mode != "seeded_research":
        return {"trace_events": [_emit(
            "tailor_skill_adapter", t0,
            {"entry_mode": entry_mode, "activated": False},
            {"skipped": True, "verdict": "skipped", "generated_by": "n/a"},
            [], "n/a", [],
            state_keys=["tailored_method", "trace_events", "reasoning_ledger"],
        )]}

    prompt = build_tailor_prompt(state)
    raw: dict[str, Any] | None = None
    prov = "premium_review"

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system=_TAILOR_SYSTEM,
            node_name="tailor_skill_adapter",
            profile="premium_review",
            contract_id="tailor-skill/v1",
            max_tokens=3000,
            timeout=60.0,
            fallback=None,  # we manage fallback ourselves for trace visibility
        )
        if not isinstance(raw, dict):
            logger.warning("tailor_skill_adapter: LLM returned non-dict, using fallback")
            raw = None
    except Exception as exc:
        logger.warning("tailor_skill_adapter: LLM call failed: %s — using rule fallback", exc)
        prov = "fallback"

    if raw is None:
        result = _fallback_tailor(state)
        result["generated_by"] = "fallback"
        prov = "fallback"
    else:
        result = _normalize_tailor_output(raw)
        result["generated_by"] = "llm"

    # Re8.1 WP3: non-blocking output quality validation.
    # Attaches ``_validation`` report to tailored_method and logs warnings
    # when gates fail. Does NOT block the pipeline — downstream
    # reflection_gates may consume ``_validation`` for repair decisions.
    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            validate_tailor_output,
        )
        validation_report = validate_tailor_output(
            result, state.get("seed_cards") or []
        )
        result["_validation"] = validation_report
        if not validation_report.get("overall_passed"):
            failed_gates = {
                k: v for k, v in validation_report.items()
                if isinstance(v, dict) and not v.get("passed", True)
            }
            logger.warning(
                "tailor_skill_adapter: output validation gates failed: %s",
                failed_gates,
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("tailor_skill_adapter: validation error: %s", exc)

    # Append ReasoningLedgerEntry (WP6 preview — stage="tailor")
    ledger_entry = _make_tailor_ledger(state, result)
    existing_ledger = list(state.get("reasoning_ledger") or [])

    trace = _emit(
        "tailor_skill_adapter", t0,
        {
            "entry_mode": entry_mode,
            "n_seed_cards": len(state.get("seed_cards") or []),
            "n_families": len(state.get("method_families") or []),
            "n_lanes": len(state.get("search_lanes") or []),
            "n_gaps_open": sum(1 for g in (state.get("evidence_gaps") or [])
                                if g.get("status") in ("open", "partially_satisfied")),
        },
        {
            "verdict": result["verdict"],
            "generated_by": result["generated_by"],
            "n_candidate_modules": len(result["candidate_modules"]),
            "n_ablation_rows": len(result["ablation_matrix"]),
            "n_research_gaps": len(result["evidence_gaps_for_research"]),
        },
        [{"tool": "tailor-skill/v1" if prov != "fallback" else "rule-fallback"}],
        prov, [],
        state_keys=["tailored_method", "trace_events", "reasoning_ledger"],
    )

    return {
        "tailored_method": result,
        "reasoning_ledger": existing_ledger + [ledger_entry],
        "trace_events": [trace],
    }


def _make_tailor_ledger(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Build a ReasoningLedgerEntry for the Tailor decision."""
    from apps.api.app.services.agents.graph.re80_schema import make_ledger_entry
    seed_ids = [c.get("seed_id", "") for c in (state.get("seed_cards") or [])][:3]
    return make_ledger_entry(
        decision_id=f"tailor-{int(time.time() * 1000) % 100000}",
        stage="tailor",
        decision=f"verdict={result['verdict']}; "
                 f"primary_baseline={result['primary_baseline'].get('title', '')[:80]}",
        evidence_ids=seed_ids,
        alternatives_considered=[m.get("name", "") for m in result["candidate_modules"][:3]],
        hypothesis=result.get("assembly_plan", {}).get("description", "")[:200] or None,
        next_action=("issue GO" if result["verdict"] == "GO"
                     else "request re-search" if result["evidence_gaps_for_research"]
                     else "revise and retry"),
        confidence=0.4 if result.get("generated_by") == "fallback" else 0.7,
        status="proposed",
    )
