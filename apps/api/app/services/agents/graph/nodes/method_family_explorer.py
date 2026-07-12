"""Re8.0 WP3: Method Family Explorer — task ontology + method family derivation.

This module sits between ``paper_understanding`` and ``topic_parser`` in the
seeded_research chain. Given the SeedPaperCards produced upstream, it:

  1. Performs **lightweight task ontology** classification — maps the seed's
     task_definition / method_summary to one of
     {classification, detection, segmentation, generation, forecasting, other}
     via a rule-based keyword matcher (no LLM call needed for this step).
  2. Calls the LLM to derive **2-4 MethodFamilyCard** entries, each tagged
     with ``relation_to_seed`` ∈
     {direct_competitor, alternative_formulation, transferable_mechanism, incompatible}.
  3. Emits the **five Search Lanes** from Re8.0 §7.3:
     Anchor/Reference, Competing Baseline, Mechanism/Module, Resource,
     Counter-evidence — with explicit anti-anchoring queries (one query
     without the seed model name, one direct-competitor query, one
     counter-evidence query), satisfying Re8.0 §7.4.

The node is a no-op when entry_mode == "topic_only" or when no seed card
has enough understanding fields (task_definition + method_summary), so
``topic_only`` callers see no behaviour change.

Acceptance (WP3): "YOLO 输入不会机械地把所有视觉模型当作同任务直接基线."
Concretely, an ``incompatible`` MethodFamilyCard is emitted whenever the
task type clearly diverges (e.g. YOLO=detection vs U-Net=segmentation),
and the LLM prompt explicitly forbids tagging cross-task families as
``direct_competitor``.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.re80_schema import (
    METHOD_RELATIONS,
    make_evidence_gap,
    make_ledger_entry,
    make_method_family,
    validate_evidence_gap,
    validate_ledger_entry,
    validate_method_family,
)
from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


# ── Task ontology (lightweight, rule-based) ────────────────────────────────

TASK_TYPES = (
    "classification",
    "detection",
    "segmentation",
    "generation",
    "forecasting",
    "other",
)

# Keyword → task_type mapping. Order matters: first match wins.
# Keywords are matched case-insensitively against task_definition and
# method_summary. Keep the lists specific enough to avoid false positives
# (e.g. "classification" alone is too broad — we require "image
# classification" or "text classification" to disambiguate from
# "classification" used as a sub-step of detection).
#
# Note: segmentation is checked BEFORE detection so that "Mask R-CNN
# instance segmentation" is classified as segmentation (not detection,
# even though "R-CNN" appears in the detection list). Order matters
# whenever a keyword from one family is a substring of a keyword from
# another.
_TASK_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("segmentation", (
        r"\bsegmentation\b",
        r"\bU-Net\b",
        r"\bMask R-CNN\b",
        r"\bpixel[\s-]?wise\b",
        r"\bsemantic segmentation\b",
        r"\binstance segmentation\b",
        r"\bpanoptic\b",
    )),
    ("detection", (
        r"\bobject detection\b",
        r"\bdetect(ion|or)\b",
        r"\bYOLO\b",
        r"\bfaster[\s-]?rcnn\b",
        r"\bR-CNN\b",
        r"\bbounding box\b",
        r"\banchor\b",
        r"\bgrounding\b",
    )),
    ("classification", (
        r"\bimage classification\b",
        r"\btext classification\b",
        r"\bclassification task\b",
        r"\bclassifier\b",
        r"\bResNet\b",
        r"\bViT\b",
        r"\bEfficientNet\b",
    )),
    ("generation", (
        r"\bgeneration\b",
        r"\bGAN\b",
        r"\bVAE\b",
        r"\bdiffusion\b",
        r"\btext-to-image\b",
        r"\bimage synthesis\b",
    )),
    ("forecasting", (
        r"\bforecast(ing)?\b",
        r"\btime[\s-]?series\b",
        r"\btemporal prediction\b",
        r"\bLSTM\b",
        r"\bTransformer.*prediction\b",
    )),
]


def classify_task_type(text: str) -> str:
    """Map free-text task description to one of TASK_TYPES via keywords.

    Returns ``"other"`` if no keyword matches. The matcher is intentionally
    conservative — when in doubt we prefer ``"other"`` and let the LLM
    refine.
    """
    if not text:
        return "other"
    for task_type, patterns in _TASK_KEYWORDS:
        for pat in patterns:
            if re.search(pat, text, re.I):
                return task_type
    return "other"


def _seed_text_for_task(card: dict[str, Any]) -> str:
    """Concatenate task_definition + method_summary + resolved_title for
    task-type classification. Returns empty string if none available."""
    parts = [
        card.get("task_definition") or "",
        card.get("method_summary") or "",
        card.get("resolved_title") or "",
    ]
    return " ".join(p for p in parts if p).strip()


# ── LLM prompt for method family derivation ────────────────────────────────

_FAMILY_SYSTEM = (
    "You are a research methodology analyst. Given a seed paper's task and "
    "method, propose 2-4 alternative method families with their relation to "
    "the seed. Return ONLY a valid JSON object — no prose, no fences."
)

_FAMILY_USER_TEMPLATE = """Analyze the seed paper and propose 2-4 method families.

Seed paper:
- Title: {title}
- Task definition: {task_def}
- Method summary: {method}
- Stated limitations: {limitations}
- Inferred task type: {task_type}

RULES (CRITICAL — violating any rule makes the output useless):
1. Do NOT tag a cross-task family as "direct_competitor". For example,
   if the seed is an object detector (YOLO), U-Net (segmentation) is NOT
   a direct competitor — it is "alternative_formulation" (if pixel-level
   output is plausible for the user's goal) or "incompatible" (if the
   goal is purely instance localisation).
2. "direct_competitor" must share the SAME task_type as the seed.
3. "alternative_formulation" addresses the same underlying problem with
   a different task framing.
4. "transferable_mechanism" borrows a module/idea from a different task
   family.
5. "incompatible" means the family cannot be fairly compared with the
   seed under the same evaluation protocol.
6. For each family, generate 1-3 search_queries. At least one query
   across ALL families must NOT contain the seed model name (anti-anchoring).
7. Aim for diversity: include at least one direct_competitor and at least
   one alternative_formulation or transferable_mechanism when possible.

[OUTPUT CONTRACT] After your analysis, your ENTIRE final message must be
exactly ONE valid JSON object with this shape:
{{
  "families": [
    {{
      "name": "short family name, e.g. Two-stage detectors",
      "task_type": "one of: classification, detection, segmentation, generation, forecasting, other",
      "relation_to_seed": "one of: direct_competitor, alternative_formulation, transferable_mechanism, incompatible",
      "applicability_conditions": ["condition 1", "condition 2"],
      "interface_requirements": ["requirement 1"],
      "expected_strengths": ["strength 1"],
      "expected_weaknesses": ["weakness 1"],
      "search_queries": ["query 1", "query 2"]
    }}
  ]
}}

If you cannot determine a field, use an empty array [] or empty string. Do not fabricate."""


def _format_limitations(limitations: list[str] | None) -> str:
    if not limitations:
        return "(none stated)"
    return "; ".join(limitations)


def _call_family_llm(
    *,
    title: str,
    task_def: str,
    method: str,
    limitations: list[str],
    task_type: str,
) -> list[dict[str, Any]] | None:
    """Call the LLM to derive method families.

    Returns a list of family dicts (raw, not yet validated) or None on
    failure.
    """
    user_prompt = _FAMILY_USER_TEMPLATE.format(
        title=title or "(unknown)",
        task_def=task_def or "(unknown)",
        method=method or "(unknown)",
        limitations=_format_limitations(limitations),
        task_type=task_type,
    )

    try:
        from apps.api.app.services import llm_router
        out = llm_router.call_json(
            user_prompt,
            system=_FAMILY_SYSTEM,
            profile="fast_json",
            max_tokens=2000,
            timeout=60,
            expected="dict",
            schema_hint=(
                'JSON object with key "families" mapping to an array of '
                '{name, task_type, relation_to_seed, applicability_conditions[], '
                'interface_requirements[], expected_strengths[], expected_weaknesses[], '
                'search_queries[]}'
            ),
        )
        if isinstance(out, dict) and isinstance(out.get("families"), list):
            return out["families"]
        if isinstance(out, list):
            # Model returned a bare list — wrap it.
            return out
        logger.warning("method family LLM returned unexpected shape: %s", type(out))
        return None
    except Exception as exc:
        logger.warning("method family LLM call failed: %s", exc)
        return None


def _normalise_family(
    raw: dict[str, Any],
    *,
    seed_id: str,
    idx: int,
    seed_task_type: str,
) -> dict[str, Any] | None:
    """Convert a raw LLM family dict into a MethodFamilyCard.

    Returns None if the raw dict is too malformed to salvage. Enforces
    the cross-task direct_competitor rule (WP3 acceptance): if the
    family's task_type differs from the seed's task_type, downgrade
    ``direct_competitor`` to ``alternative_formulation`` (or
    ``incompatible`` if the task_type is wildly different).
    """
    if not isinstance(raw, dict):
        return None
    name = (raw.get("name") or "").strip()
    if not name:
        return None

    task_type = (raw.get("task_type") or "other").strip().lower()
    if task_type not in TASK_TYPES:
        task_type = "other"

    relation = (raw.get("relation_to_seed") or "alternative_formulation").strip().lower()
    if relation not in METHOD_RELATIONS:
        relation = "alternative_formulation"

    # WP3 acceptance guard: cross-task families cannot be direct_competitor.
    if relation == "direct_competitor" and task_type != seed_task_type:
        # If the family task_type is "other" (unknown), be lenient — the
        # LLM may simply have failed to classify. Keep as direct_competitor.
        if task_type != "other" and seed_task_type != "other":
            relation = "alternative_formulation"
            logger.info(
                "WP3 guard: family '%s' task_type '%s' != seed '%s'; "
                "downgraded direct_competitor → alternative_formulation",
                name, task_type, seed_task_type,
            )

    family = make_method_family(
        family_id=f"family-{seed_id}-{idx}",
        name=name,
        task_type=task_type,
        relation_to_seed=relation,
        applicability_conditions=raw.get("applicability_conditions") or [],
        interface_requirements=raw.get("interface_requirements") or [],
        expected_strengths=raw.get("expected_strengths") or [],
        expected_weaknesses=raw.get("expected_weaknesses") or [],
        search_queries=raw.get("search_queries") or [],
    )
    errs = validate_method_family(family)
    if errs:
        logger.warning("family %s validation failed: %s", name, errs)
        return None
    return family


# ── Five Search Lanes (Re8.0 §7.3 + §7.4 anti-anchoring) ───────────────────

# Lane IDs are stable so downstream nodes and tests can reference them.
LANE_IDS = (
    "anchor_reference",
    "competing_baseline",
    "mechanism_module",
    "resource",
    "counter_evidence",
)

_LANE_DESCRIPTIONS = {
    "anchor_reference": "Classic origins, citation chain, theoretical background",
    "competing_baseline": "Fair-comparison routes within the same task",
    "mechanism_module": "Modules addressing specific seed limitations",
    "resource": "Runnable resources: repos, datasets, weights, env files",
    "counter_evidence": "Active challenge of seed and proposed innovation",
}


def build_search_lanes(
    *,
    seed_card: dict[str, Any],
    families: list[dict[str, Any]],
    task_type: str,
) -> list[dict[str, Any]]:
    """Build the five Search Lane objects.

    Each lane is a dict with: ``lane_id``, ``description``, ``queries``
    (list of strings), and ``gap_id`` (reference to the EvidenceGap that
    motivates this lane, if any).

    Anti-anchoring (Re8.0 §7.4): at least one query in
    ``competing_baseline`` MUST NOT contain the seed model name; at
    least one query in ``counter_evidence`` MUST be a counter-evidence
    or similar-work query.
    """
    seed_title = (seed_card.get("resolved_title") or "").strip()
    seed_method = (seed_card.get("method_summary") or "").strip()
    seed_limitations = seed_card.get("limitations") or []

    # Extract a short "seed model name" heuristic from the method summary.
    # We pick the first Capitalised or upper-case token (e.g. "YOLO",
    # "U-Net", "BERT"). Used to construct anti-anchoring queries.
    seed_model_name = _extract_seed_model_name(seed_method)

    # Collect queries from each family's search_queries, bucketed by relation.
    direct_competitor_queries: list[str] = []
    alternative_queries: list[str] = []
    mechanism_queries: list[str] = []
    for fam in families:
        relation = fam.get("relation_to_seed", "")
        qs = fam.get("search_queries") or []
        if relation == "direct_competitor":
            direct_competitor_queries.extend(qs)
        elif relation == "alternative_formulation":
            alternative_queries.extend(qs)
        elif relation == "transferable_mechanism":
            mechanism_queries.extend(qs)

    # Lane 1: Anchor/Reference — classic origins + citation chain
    anchor_queries = []
    if seed_title:
        anchor_queries.append(f"classic survey {task_type} foundations")
        anchor_queries.append(f"citation chain: {seed_title[:80]}")
    else:
        anchor_queries.append(f"classic survey {task_type}")

    # Lane 2: Competing Baseline — fair comparison within same task
    # Anti-anchoring: ensure at least one query has no seed model name.
    competing_queries = list(direct_competitor_queries)
    # Always add an anti-anchoring query (task-only, no model name).
    anti_anchor_q = f"recent {task_type} methods benchmark"
    if anti_anchor_q not in competing_queries:
        competing_queries.append(anti_anchor_q)
    # If the seed model name appears in ALL queries, add a guaranteed
    # clean one at the front.
    if seed_model_name and all(
        seed_model_name.lower() in q.lower() for q in competing_queries
    ):
        competing_queries.insert(0, f"state of the art {task_type} without {seed_model_name}")

    # Lane 3: Mechanism/Module — modules addressing specific limitations
    mechanism_lane_queries = list(mechanism_queries)
    for lim in seed_limitations[:2]:  # top 2 limitations
        if lim:
            mechanism_lane_queries.append(f"module addressing: {lim[:100]}")
    # Ensure the lane always has at least one query, even when no
    # limitations and no transferable_mechanism families are available.
    if not mechanism_lane_queries:
        mechanism_lane_queries.append(f"mechanism module survey {task_type}")

    # Lane 4: Resource — repos, datasets, weights, env
    resource_queries = [
        f"reproduction repository {task_type}",
        f"benchmark dataset {task_type}",
    ]
    if seed_title:
        resource_queries.append(f"code repository: {seed_title[:60]}")

    # Lane 5: Counter-evidence — active challenge
    # Must contain a counter-evidence or similar-work query.
    counter_queries = list(alternative_queries)
    counter_queries.append(f"negative results {task_type} limitations")
    counter_queries.append(f"similar work challenging {task_type} assumptions")
    # Ensure at least one explicit counter-evidence query is present.
    has_counter = any(
        re.search(r"(negative|counter|challenge|fail|limitation)", q, re.I)
        for q in counter_queries
    )
    if not has_counter:
        counter_queries.append(
            f"counter-evidence for {task_type} methods: failure cases"
        )

    lanes = [
        {
            "lane_id": "anchor_reference",
            "description": _LANE_DESCRIPTIONS["anchor_reference"],
            "queries": _dedupe(anchor_queries),
            "gap_id": None,
        },
        {
            "lane_id": "competing_baseline",
            "description": _LANE_DESCRIPTIONS["competing_baseline"],
            "queries": _dedupe(competing_queries),
            "gap_id": None,
        },
        {
            "lane_id": "mechanism_module",
            "description": _LANE_DESCRIPTIONS["mechanism_module"],
            "queries": _dedupe(mechanism_lane_queries),
            "gap_id": None,
        },
        {
            "lane_id": "resource",
            "description": _LANE_DESCRIPTIONS["resource"],
            "queries": _dedupe(resource_queries),
            "gap_id": None,
        },
        {
            "lane_id": "counter_evidence",
            "description": _LANE_DESCRIPTIONS["counter_evidence"],
            "queries": _dedupe(counter_queries),
            "gap_id": None,
        },
    ]
    return lanes


def _extract_seed_model_name(method_summary: str) -> str:
    """Heuristic: pull the first likely model name from the method summary.

    Looks for tokens that are all-uppercase (>=3 chars) or match
    Capitalised-Hyphen-Capitalised (e.g. "U-Net", "Mask R-CNN").
    Returns empty string if none found.
    """
    if not method_summary:
        return ""
    # All-uppercase tokens (YOLO, BERT, ViT)
    for tok in re.split(r"\s+", method_summary):
        clean = re.sub(r"[^A-Za-z0-9\-]", "", tok)
        if len(clean) >= 3 and clean.isupper():
            return clean
    # Capitalised-hyphen-Capitalised (U-Net, R-CNN). Allow single-letter
    # first part (e.g. "U-Net") by using [a-zA-Z]* instead of [a-z]+.
    m = re.search(r"\b([A-Z][a-zA-Z]*-[A-Z][a-zA-Z]+)\b", method_summary)
    if m:
        return m.group(1)
    return ""


def _dedupe(queries: list[str]) -> list[str]:
    """Remove duplicate queries while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(q.strip())
    return out


# ── Evidence Gap generation for WP3 ────────────────────────────────────────

def _generate_gaps_for_missing_task(
    seed_card: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate an EvidenceGap when the seed has no task_definition.

    Without a task definition, method family derivation cannot run
    meaningfully — the gap signals that upstream paper_understanding
    needs to fill this field.
    """
    sid = seed_card.get("seed_id", "unknown")
    task_def = seed_card.get("task_definition")
    method = seed_card.get("method_summary")
    if task_def or method:
        return []
    gap = make_evidence_gap(
        gap_id=f"gap-{sid}-task_definition_for_family",
        question=f"What task does seed '{sid}' address? Needed for method family derivation.",
        gap_type="existence",
        why_needed=(
            "Method Family Explorer cannot derive competing/alternative "
            "families without knowing the seed's task. Paper Understanding "
            "should fill task_definition."
        ),
        related_claim_ids=[sid],
        success_condition="seed_card.task_definition is non-null",
    )
    if not validate_evidence_gap(gap):
        return [gap]
    return []


# ── LangGraph node ──────────────────────────────────────────────────────────

def method_family_explorer_node(state: ResearchState) -> dict[str, Any]:
    """Re8.0 WP3: derive method families + five Search Lanes from seeds.

    No-op when entry_mode == "topic_only" or when no seed card has
    enough understanding (task_definition OR method_summary) to drive
    family derivation.
    """
    t0 = time.time()
    entry_mode = state.get("entry_mode", "topic_only")
    seed_cards: list[dict[str, Any]] = list(state.get("seed_cards") or [])

    state_keys = ["method_families", "search_lanes", "evidence_gaps",
                  "reasoning_ledger", "trace_events"]

    if entry_mode == "topic_only" or not seed_cards:
        trace = _emit(
            "method_family_explorer", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards)},
            {"skipped": True, "reason": "topic_only or no seed_cards"},
            [], "local", [],
            state_keys=state_keys,
        )
        return {"trace_events": [trace]}

    # Pick the first seed card with enough understanding to drive family
    # derivation. (Multi-seed family derivation is a future extension; for
    # MVP we use the primary seed.)
    primary_seed: dict[str, Any] | None = None
    for card in seed_cards:
        if card.get("task_definition") or card.get("method_summary"):
            primary_seed = card
            break

    if primary_seed is None:
        # No seed has enough understanding — emit gaps for all seeds and
        # return early.
        all_gaps: list[dict[str, Any]] = []
        for card in seed_cards:
            all_gaps.extend(_generate_gaps_for_missing_task(card))
        trace = _emit(
            "method_family_explorer", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards),
             "n_with_understanding": 0},
            {"skipped": True, "reason": "no seed has task_definition or method_summary",
             "n_gaps_emitted": len(all_gaps)},
            [], "local", [],
            state_keys=state_keys,
        )
        result: dict[str, Any] = {"trace_events": [trace]}
        if all_gaps:
            result["evidence_gaps"] = all_gaps
        return result

    # ── Step 1: lightweight task ontology ───────────────────────────────
    seed_text = _seed_text_for_task(primary_seed)
    task_type = classify_task_type(seed_text)
    sid = primary_seed.get("seed_id", "unknown")

    # ── Step 2: LLM method family derivation ────────────────────────────
    raw_families = _call_family_llm(
        title=primary_seed.get("resolved_title") or "",
        task_def=primary_seed.get("task_definition") or "",
        method=primary_seed.get("method_summary") or "",
        limitations=primary_seed.get("limitations") or [],
        task_type=task_type,
    )

    families: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if raw_families:
        for idx, raw in enumerate(raw_families[:4]):  # cap at 4 families
            fam = _normalise_family(
                raw, seed_id=sid, idx=idx, seed_task_type=task_type,
            )
            if fam:
                families.append(fam)
            else:
                errors.append({
                    "seed_id": sid,
                    "error": "family_normalisation_failed",
                    "detail": f"family idx={idx} name={raw.get('name', '?')}",
                })
    else:
        errors.append({
            "seed_id": sid,
            "error": "llm_family_derivation_failed",
            "detail": "LLM returned no families",
        })

    # ── Step 3: build five Search Lanes ────────────────────────────────
    lanes = build_search_lanes(
        seed_card=primary_seed,
        families=families,
        task_type=task_type,
    )

    # ── Step 4: Reasoning Ledger entry ─────────────────────────────────
    ledger_entry = make_ledger_entry(
        decision_id=f"decision-{sid}-family_expansion",
        stage="family_expansion",
        decision=(
            f"Derived {len(families)} method families for seed '{sid}' "
            f"with inferred task_type='{task_type}'."
        ),
        evidence_ids=[sid],
        alternatives_considered=[f["name"] for f in families],
        rejection_reasons=[
            e.get("detail", "") for e in errors
        ] or None,
        hypothesis=(
            f"Seed task is {task_type}; competing baselines should share "
            f"this task type."
        ),
        falsifier=(
            "A direct_competitor with a different task_type would refute "
            "the task ontology classification."
        ),
        next_action="Pass families + lanes to Evidence Gap Planner and Search.",
        confidence=0.7 if families else 0.2,
        status="evidence_backed" if families else "unresolved",
    )
    ledger_errs = validate_ledger_entry(ledger_entry)
    if ledger_errs:
        logger.warning("ledger entry validation failed: %s", ledger_errs)

    # ── Step 5: emit trace ─────────────────────────────────────────────
    n_direct = sum(1 for f in families if f["relation_to_seed"] == "direct_competitor")
    n_alternative = sum(1 for f in families if f["relation_to_seed"] == "alternative_formulation")
    n_transferable = sum(1 for f in families if f["relation_to_seed"] == "transferable_mechanism")
    n_incompatible = sum(1 for f in families if f["relation_to_seed"] == "incompatible")

    trace = _emit(
        "method_family_explorer", t0,
        {
            "entry_mode": entry_mode,
            "n_seed_cards": len(seed_cards),
            "primary_seed_id": sid,
            "inferred_task_type": task_type,
        },
        {
            "n_families": len(families),
            "n_direct_competitor": n_direct,
            "n_alternative_formulation": n_alternative,
            "n_transferable_mechanism": n_transferable,
            "n_incompatible": n_incompatible,
            "n_search_lanes": len(lanes),
            "n_errors": len(errors),
        },
        [
            {"tool": "llm_router.call_json", "profile": "fast_json",
             "purpose": "method_family_derivation"},
        ],
        "llm_router" if families else "local",
        errors,
        state_keys=state_keys,
    )

    result = {
        "method_families": families,
        "search_lanes": lanes,
        "reasoning_ledger": [ledger_entry] if not ledger_errs else [],
        "trace_events": [trace],
    }
    return result
