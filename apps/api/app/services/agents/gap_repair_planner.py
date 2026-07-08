"""Re08 GapRepairPlanner — SOP §4.3.

Generates 1-3 targeted queries per ``gap_reasons`` item.  Built on top of
the rule layer (no LLM call in offline mode) so the re-audit can run on
the Balanced40 raw dumps without burning quota.

Two layers:
  * ``rule_repair_plan`` — deterministic: every gap_reason has a
    pre-mapped query template; we instantiate it from topic_atoms.
  * ``llm_repair_plan``  — async; uses ``GAP_REPAIR_PLANNER_SYSTEM``
    prompt to override / refine the rule plan when LLM is enabled.

The planner is intentionally a *function* that returns a dict, not an
LLM agent — Re08 SOP §10 says "only execute sessions that have an SOP,
do not invent new-session roadmaps" so we keep the surface narrow.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

from .prompts.gap_repair_planner import render_gap_repair

logger = logging.getLogger(__name__)


# ponytail: placeholder leak — drop queries that still carry unsubstituted
# {task}/{object}/{scenario}/... slots, or the literal "X" sentinel.
_PLACEHOLDER_RE = re.compile(r"[{}]|\bX\b")
# axial atoms the planner tries to expand; if all of these are empty for
# the current ``topic_atoms`` the rule layer cannot produce real queries.
_ATOM_AXES = ("task", "object", "method", "scenario")


# ---------------------------------------------------------------------------
# Rule layer: gap → query templates
# ---------------------------------------------------------------------------

# Each entry maps a gap reason (verbatim from compute_resource_status
# evidence_gap_reasons) to a list of (target_role, query_template)
# tuples.  Query templates use {task}, {object}, {method}, {scenario}
# as placeholders.

_GAP_QUERY_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "no_dataset_or_data_gap_note": [
        ("dataset", "{object} dataset benchmark"),
        ("dataset", "{object} {scenario} dataset collection"),
        ("repo", "{object} {task} implementation github"),
    ],
    "datasets_present_but_no_topic_dataset": [
        ("dataset", "{object} {scenario} benchmark"),
        ("dataset", "{object} {task} real-world dataset"),
        ("parallel_paper", "{object} {task} {method} survey"),
    ],
    "scenario_axis_missing": [
        ("parallel_paper", "{object} {scenario} detection"),
        ("parallel_paper", "{scenario} {method} {object}"),
        ("dataset", "{scenario} {object} dataset"),
    ],
    "attack_defense_axis_missing": [
        ("parallel_paper", "adversarial attack {object} detection"),
        ("parallel_paper", "{method} robustness {object} defense"),
        ("parallel_paper", "evasion patch {task} mitigation"),
    ],
    "object_axis_missing": [
        ("baseline", "{object} {task} benchmark"),
        ("dataset", "{object} public dataset"),
        ("repo", "{object} {task} github implementation"),
    ],
    "core_n=1_but_no_effective_core": [
        ("core_paper", "{object} {task} {method} survey"),
        ("core_paper", "{object} {task} benchmark paper"),
        ("parallel_paper", "{object} {task} state-of-the-art"),
    ],
    "no_effective_evidence_at_all": [
        ("baseline", "{object} {task} {method}"),
        ("parallel_paper", "{object} {task} recent paper"),
        ("dataset", "{object} {task} public benchmark"),
    ],
}


def _flatten_first_atom(topic_atoms: dict, axis: str) -> str:
    """Return the first English atom (en or string) for axis, or empty."""
    atoms = topic_atoms.get(axis) or []
    for a in atoms:
        if isinstance(a, dict):
            v = a.get("en") or a.get("zh")
            if v:
                return str(v)
        elif isinstance(a, str) and a:
            return a
    return ""


def _build_query(template: str, topic_atoms: dict) -> str:
    """Substitute {task}/{object}/{method}/{scenario} placeholders."""
    placeholders = {
        "task": _flatten_first_atom(topic_atoms, "task"),
        "object": _flatten_first_atom(topic_atoms, "object"),
        "method": _flatten_first_atom(topic_atoms, "method"),
        "scenario": _flatten_first_atom(topic_atoms, "scenario"),
    }
    out = template
    for k, v in placeholders.items():
        out = out.replace("{" + k + "}", v or "X")
    # Collapse repeated spaces, drop empty placeholder residue.
    out = " ".join(out.split())
    return out


def _has_any_atom(topic_atoms: dict) -> bool:
    """True when ``topic_atoms`` has at least one non-empty axis value."""
    for axis in _ATOM_AXES:
        atoms = topic_atoms.get(axis) or []
        for a in atoms:
            if isinstance(a, dict) and (a.get("en") or a.get("zh")):
                return True
            if isinstance(a, str) and a.strip():
                return True
    return False


def rule_repair_plan(
    gap_reasons: list[str],
    topic_atoms: dict,
) -> list[dict]:
    """Generate a repair plan from the rule templates only.

    Returns a list of ``{gap, target_role, queries[]}`` items, one per
    gap reason that has a matching template.  Unmatched gaps are noted
    in the ``unrepairable_reason`` field of the wrapper dict.

    Re09 SOP \\xc2\\xa74.4 — queries containing unsubstituted
    ``{...}`` placeholders or the literal ``X`` sentinel are dropped.
    If a gap ends up with zero valid queries the gap is not emitted.
    """
    plan: list[dict] = []
    unmatched: list[str] = []
    placeholder_drops: list[tuple[str, str]] = []
    for gap in gap_reasons or []:
        key = gap.strip().lower()
        tmpl_key = None
        for k in _GAP_QUERY_TEMPLATES:
            if k in key or key.startswith(k):
                tmpl_key = k
                break
        if tmpl_key is None:
            unmatched.append(gap)
            continue
        queries: list[dict] = []
        for target_role, tmpl in _GAP_QUERY_TEMPLATES[tmpl_key][:3]:
            rendered = _build_query(tmpl, topic_atoms)
            if _PLACEHOLDER_RE.search(rendered):
                placeholder_drops.append((gap, rendered))
                logger.warning(
                    "rule_repair_plan dropped placeholder query for gap "
                    "%r: %r", gap, rendered,
                )
                continue
            queries.append({
                "query": rendered,
                "tool": _tool_for_role(target_role),
                "why": f"targets {target_role}; closes '{tmpl_key}'",
            })
        if queries:
            plan.append({
                "gap": gap,
                "target_role": _GAP_QUERY_TEMPLATES[tmpl_key][0][0],
                "queries": queries,
            })
        else:
            unmatched.append(gap)
    return plan, unmatched, placeholder_drops


def _tool_for_role(role: str) -> str:
    return {
        "core_paper": "arxiv",
        "baseline": "openalex",
        "parallel_paper": "openalex",
        "dataset": "huggingface",
        "repo": "github",
    }.get(role, "openalex")


def build_repair_plan(
    gap_reasons: list[str],
    topic_atoms: dict,
    *,
    topic: str = "",
    candidate_summary: str = "",
    llm_client: Callable | None = None,
) -> dict:
    """Public entry point.

    Returns ``{"repair_plan": [...], "unrepairable_reason": "..."}``.
    When ``llm_client`` is None, the plan is purely rule-based; otherwise
    the LLM may refine it.
    """
    rule_plan, unmatched, dropped = rule_repair_plan(gap_reasons, topic_atoms)
    # ponytail: if rule layer has no atom coverage, refuse to emit
    # placeholder queries (SOP \\xc2\\xa74.4).
    if not _has_any_atom(topic_atoms):
        return {
            "repair_plan": [],
            "unrepairable_reason": "; ".join([
                f"gap '{g}' has no atom-coverage, needs_clarification"
                for g in (gap_reasons or [])
            ]) or "no topic_atoms; needs_clarification",
            "dropped_placeholder_queries": dropped,
        }
    if llm_client is None or not rule_plan:
        reason = "; ".join(unmatched) if unmatched else ""
        if dropped:
            reason = (
                f"{reason}; dropped {len(dropped)} placeholder queries"
                if reason else f"dropped {len(dropped)} placeholder queries"
            )
        return {
            "repair_plan": rule_plan,
            "unrepairable_reason": reason,
            "dropped_placeholder_queries": dropped,
        }
    # Otherwise async LLM refinement would happen here; kept out of the
    # Balanced40 re-audit path to preserve quota.
    return {
        "repair_plan": rule_plan,
        "unrepairable_reason": "; ".join(unmatched) if unmatched else "",
        "dropped_placeholder_queries": dropped,
    }


# ---------------------------------------------------------------------------
# Async LLM-mode (online only)
# ---------------------------------------------------------------------------


async def llm_repair_plan(
    gap_reasons: list[str],
    topic_atoms: dict,
    *,
    topic: str,
    candidate_summary: str,
    llm_client: Callable,
) -> dict:
    """Call the LLM planner for a refined plan (online)."""
    user_prompt = render_gap_repair(
        topic=topic or "",
        topic_atoms=topic_atoms,
        current_status="fail_or_weak",
        gap_reasons=gap_reasons,
        candidate_summary=candidate_summary,
    )
    try:
        raw = await llm_client(user_prompt)
        import json
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception as exc:  # ponytail: never let LLM failures kill the planner
        logger.warning("llm_repair_plan failed: %s", exc)
        return build_repair_plan(gap_reasons, topic_atoms)

    if not _has_any_atom(topic_atoms):
        return {
            "repair_plan": [],
            "unrepairable_reason": (
                "; ".join([
                    f"gap '{g}' has no atom-coverage, needs_clarification"
                    for g in (gap_reasons or [])
                ]) or "no topic_atoms; needs_clarification"
            ),
            "dropped_placeholder_queries": [],
        }
    rule = rule_repair_plan(gap_reasons, topic_atoms)
    rule_plan_only, _unmatched, _dropped = rule
    plan = payload.get("repair_plan") or []
    by_gap = {p["gap"]: p for p in plan if p.get("gap")}
    merged: list[dict] = []
    for rp in rule_plan_only:
        gap = rp["gap"]
        if gap in by_gap:
            rp2 = dict(by_gap[gap])
            rp2.setdefault("target_role", rp["target_role"])
            merged.append(rp2)
        else:
            merged.append(rp)
    for gp in plan:
        if gp.get("gap") not in {m.get("gap") for m in merged}:
            merged.append(gp)
    return {
        "repair_plan": merged,
        "unrepairable_reason": payload.get("unrepairable_reason", ""),
        "dropped_placeholder_queries": _dropped,
    }


__all__ = [
    "rule_repair_plan",
    "build_repair_plan",
    "llm_repair_plan",
]