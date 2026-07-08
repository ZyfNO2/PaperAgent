"""Re10 QueryRepairAgent — SOP §3.2 + §4.4 + §10.3.

Repair or drop bad queries.  The hard rule (SOP §4.4) is that queries
containing the literal ``X`` sentinel or unsubstituted ``{...}``
placeholders must NEVER be returned as ``repaired``.  Either they get
repaired via atom substitution, or they return ``needs_clarification``
/ ``drop``.

ponytail:
- Pure-function design (no LLM call needed for the common case).
- Heuristic substitution only — no fabricated domain terms.
- Max 3 repaired queries per input.
- One placeholder detector used by SearchReflectionLoop and
  GapRepairPlanner (kept consistent with that module's regex).
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


# Same regex as gap_repair_planner: anything that looks like a
# placeholder (curly braces) or the literal "X" sentinel.
_PLACEHOLDER_RE = re.compile(r"[{}]|\bX\b")
# Bare single-letter "X" that isn't part of a real word.
_BARE_X_RE = re.compile(r"\bX\b")
_BRACE_RE = re.compile(r"[{}]")


# ---------------------------------------------------------------------------
# Atom helpers
# ---------------------------------------------------------------------------


_ATOM_AXES = ("task", "object", "method", "scenario", "domain")


def _flatten_first_en_atom(topic_atoms: dict, *axes: str) -> str:
    for axis in axes:
        atoms = topic_atoms.get(axis) or []
        for a in atoms:
            if isinstance(a, dict):
                v = a.get("en") or a.get("zh")
                if v:
                    return str(v).strip()
            elif isinstance(a, str) and a.strip():
                return a.strip()
    return ""


def _has_any_atom(topic_atoms: dict) -> bool:
    for axis in _ATOM_AXES:
        atoms = topic_atoms.get(axis) or []
        for a in atoms:
            if isinstance(a, dict) and (a.get("en") or a.get("zh")):
                return True
            if isinstance(a, str) and a.strip():
                return True
    return False


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def repair_query(
    bad_query: str,
    topic_atoms: dict,
    domain_keywords: dict | None = None,
) -> dict:
    """Repair a bad query, or mark it for clarification/drop.

    Returns ``{status, repaired_queries, reason}``. ``status`` is one of
    ``repaired | needs_clarification | drop``.

    Hard rule: a query that still contains ``{...}`` or ``X`` is NEVER
    returned as ``repaired``.
    """
    q = (bad_query or "").strip()
    if not q:
        return {
            "status": "drop",
            "repaired_queries": [],
            "reason": "empty query",
        }

    has_brace = bool(_BRACE_RE.search(q))
    has_bare_x = bool(_BARE_X_RE.search(q))

    # No placeholder → no repair needed, but the caller may still want
    # normalisation (collapse spaces). We return the original trimmed.
    if not has_brace and not has_bare_x:
        return {
            "status": "repaired",
            "repaired_queries": [" ".join(q.split())],
            "reason": "no placeholder detected; passing through",
        }

    # SOP §4.4 hard rule: a query that still contains ``{...}`` or
    # ``X`` is NEVER returned as ``repaired`` — even with atom coverage.
    # The X / {} is a signal that the planner mis-resolved an axis; we
    # refuse to silently substitute because that would hide a real
    # topic_atom_missing bug.  Drop or needs_clarification only.
    if not _has_any_atom(topic_atoms):
        if has_brace:
            return {
                "status": "needs_clarification",
                "repaired_queries": [],
                "reason": "query has unsubstituted {axis} placeholder and topic_atoms is empty",
            }
        return {
            "status": "drop",
            "repaired_queries": [],
            "reason": "query contains bare X and topic_atoms has no English atom to substitute",
        }

    # We have atom coverage, but the hard rule still forbids returning
    # ``repaired`` for X / {} queries.  Use needs_clarification so the
    # loop can attempt atom-coverage repair upstream (in the Search
    # Planner) rather than silently fix the wrong axis.
    return {
        "status": "needs_clarification",
        "repaired_queries": [],
        "reason": (
            "query contains X/{axis} placeholder; per SOP §4.4 hard rule never returned as "
            f"repaired (has_brace={has_brace}, has_bare_x={has_bare_x})"
        ),
    }


def batch_repair(
    bad_queries: list[str],
    topic_atoms: dict,
    domain_keywords: dict | None = None,
) -> list[dict]:
    """Repair a list of queries. Caps at 3 repaired queries per input."""
    out: list[dict] = []
    for q in bad_queries or []:
        r = repair_query(q, topic_atoms, domain_keywords)
        # Cap to 3 repaired queries.
        if r.get("status") == "repaired" and len(r.get("repaired_queries") or []) > 3:
            r["repaired_queries"] = r["repaired_queries"][:3]
        out.append(r)
    return out


__all__ = ["repair_query", "batch_repair"]


# ponytail: tiny self-check.
if __name__ == "__main__":  # pragma: no cover
    atoms = {"object": [{"en": "underwater acoustic target", "zh": "水声目标"}]}
    for q in ["X dynamic scene dataset", "{object} benchmark", "valid YOLO query", "X"]:
        print(q, "->", repair_query(q, atoms, {}))
