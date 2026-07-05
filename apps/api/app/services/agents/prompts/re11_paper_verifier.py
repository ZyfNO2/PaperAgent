"""Single-candidate paper verifier prompt (Re1.2 — per-candidate call).

For Re1.2 we issue ONE candidate per call so StepFun step-3.7-flash cannot
"compress" the response to an unrelated keyword list. With a single explicit
title the model reliably emits the verdict JSON we expect.

Output schema (single object — the caller batches across candidates):
  title / verdict (accept|weak_reject|reject) / hit_keywords /
  unrelated_keywords / related_keywords / source_type /
  relation_to_topic / url_missing / needs_human_confirm / reason
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You are a strict paper verifier. Given ONE candidate and the
research topic, decide if the candidate is relevant.

RULES:
- Title MUST match the candidate title given (case-insensitive substring).
- `hit_keywords` MUST list topic-specific terms that genuinely appear in
  the candidate title or snippet. NEVER emit generic terms like "deep
  learning" or "AI" unless the candidate itself uses them.
- `relation_to_topic` is one of:
    baseline  — provides a reproducible experimental starting point.
    parallel  — same area/method with a different specific approach.
    survey    — review / survey.
    none      — unrelated.
- verdict "accept" requires relation_to_topic in (baseline, parallel) AND
  at least 1 hit_keyword.
- verdict "weak_reject" when only generic relevance.
- verdict "reject" when relation_to_topic == none.
- url_missing: true unless the candidate already carries a URL/DOI/arXiv.
- needs_human_confirm: true when relevance is ambiguous.

Reply with ONE strict JSON object — no list, no prose, no fences."""

USER_TEMPLATE = """Topic:
{topic}

Topic atoms:
- method: {method}
- object: {object}
- task: {task}
- dataset_terms: {dataset_terms}
- baseline_terms: {baseline_terms}
- avoid_terms: {avoid_terms}

Candidate to verify (ONLY this one):
- Title: {candidates_title}
- Source: {candidates_src}
- Snippet: {candidates_snippet}

Reply with exactly ONE JSON object:
{{"title": "<exact title above>", "verdict": "<accept|weak_reject|reject>",
 "hit_keywords": [...], "unrelated_keywords": [...],
 "related_keywords": [...], "source_type": "<paper|dataset|repo|survey>",
 "relation_to_topic": "<baseline|parallel|survey|none>",
 "url_missing": <true|false>, "needs_human_confirm": <true|false>,
 "reason": "<1-2 sentences>"}}"""


def build_one(topic: str, atoms: dict[str, Any], candidate: dict[str, Any]) -> dict[str, str]:
    """Build prompt for exactly one candidate (Re1.2 per-candidate API)."""
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            topic=topic,
            method=_fmt(atoms.get("method")),
            object=_fmt(atoms.get("object")),
            task=_fmt(atoms.get("task")),
            dataset_terms=_fmt(atoms.get("dataset_terms")),
            baseline_terms=_fmt(atoms.get("baseline_terms")),
            avoid_terms=_fmt(atoms.get("avoid_terms")),
            candidates_title=(candidate.get("title") or candidate.get("name") or "").strip(),
            candidates_src=candidate.get("source") or candidate.get("origin") or "?",
            candidates_snippet=(candidate.get("abstract")
                                or candidate.get("description") or "")[:300],
        ),
    }


def build(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, str]:
    """Back-compat wrapper: rebuilds to per-candidate call for the first
    candidate only; the Re1.2 caller uses `build_one` directly."""
    if not candidates:
        return {"system": SYSTEM, "user": "(no candidates)"}
    return build_one(topic, atoms, candidates[0])


def _fmt(v: Any) -> str:
    if not v:
        return "[]"
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    return str(v)
