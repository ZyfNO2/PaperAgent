"""seed_relevance — light-weight relevance gate for citation_expand seeds.

Re03 SOP §1.3: `_seed_candidates()` only checks whether a candidate has
an openalex_id / doi / arxiv_id, not whether it is relevant to the topic.
Case A v3 then picked a "cosmic ray at CERN" paper as seed, whose
references polluted the pool.

This module does NOT call the network, NOT call the LLM, NOT modify
the CandidatePool, NOT use any blacklist. It only inspects the candidate
title + abstract + source query against the parsed_topic and emits:

    {
        "candidate_id":  "...",
        "seed_eligible": True/False,
        "matched_axis":  "method_task" | "object_task" | "method_object" |
                         "task_only" | "method_only" | "none",
        "matched_terms": [...],
        "rejected_reason": str | None,
    }

Minimal eligibility rules (any one is enough):

    1. method_terms has >= 1 hit in (title + abstract) AND
       task_terms or object_terms has >= 1 hit
    2. query_atoms_en has >= 2 keyword-groups that overlap (title/abstract)
    3. ER is already core (caller passes reviews map)

Ponytail: ~120 lines, no I/O, no LLM, no blacklist. Reject reason is
stringly-typed so we can extend without breaking tests.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable


def _norm(text: str) -> str:
    return (text or "").lower()


def _tokens(text: str) -> set[str]:
    """Lowercase whitespace-split tokens, ≥ 2 chars, alphanumeric only."""
    return {t for t in re.findall(r"[a-z0-9一-鿿]{2,}", _norm(text))}


def _hit_count(
    terms: Iterable[str], haystack_tokens: set[str],
) -> tuple[int, list[str], list[str]]:
    """Score each term against the haystack.

    Re04-fix SOP §3: multi-word terms use OR-like matching — a term
    "visual SLAM" is satisfied when ≥ ceil(N/2) of its words appear in
    the haystack. Strict ALL-AND matching misses a seed like
    "Visual Odometry Based on CNN" for "visual SLAM" (slam missing).

    Returns: (n_hits, hit_terms, threshold_matched_terms).
    """
    hits: list[str] = []
    threshold_hits: list[str] = []
    for t in terms:
        if not t:
            continue
        tl = t.lower().strip()
        if not tl:
            continue
        words = re.findall(r"[a-z0-9一-鿿]{2,}", tl)
        if not words:
            continue
        matched = [w for w in words if w in haystack_tokens]
        if len(matched) == len(words):
            hits.append(t)
        elif len(matched) >= math.ceil(len(words) / 2):
            # Re04-fix: OR-like threshold fallback.
            # Marked distinctly so the caller can label `matched_axis_threshold`.
            threshold_hits.append(t)
    return len(hits), hits, threshold_hits


def _core_ids(reviews: list[dict[str, Any]] | None) -> set[str]:
    if not reviews:
        return set()
    return {r.get("candidate_id") for r in reviews if r.get("status") == "core"}


def evaluate_seed(
    *,
    candidate: dict[str, Any],
    parsed_topic: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the seed-eligibility verdict for one candidate.

    candidate keys used: candidate_id, title, abstract, source_query.
    parsed_topic keys used: method_terms, task_terms, object_terms,
    query_atoms_en.
    """
    cid = candidate.get("candidate_id") or candidate.get("stable_id") or ""
    title = candidate.get("title") or ""
    abstract = candidate.get("abstract") or ""
    source_query = candidate.get("source_query") or ""
    haystack = _tokens(title + " " + abstract + " " + source_query)
    if not haystack:
        return {
            "candidate_id": cid,
            "seed_eligible": False,
            "matched_axis": "none",
            "matched_terms": [],
            "rejected_reason": "empty_title_abstract_source_query",
        }

    method_terms = parsed_topic.get("method_terms") or []
    task_terms = parsed_topic.get("task_terms") or []
    object_terms = parsed_topic.get("object_terms") or []
    query_atoms = parsed_topic.get("query_atoms_en") or []

    method_hits, method_matched, method_threshold = _hit_count(method_terms, haystack)
    task_hits, task_matched, task_threshold = _hit_count(task_terms, haystack)
    object_hits, object_matched, object_threshold = _hit_count(object_terms, haystack)
    atom_hits, atom_matched, atom_threshold = _hit_count(query_atoms, haystack)

    matched_terms: list[str] = []
    matched_axis = "none"
    matched_mode = "strict"
    rejected_reason: str | None = None

    # Rule 1: method + (task or object)
    if method_hits >= 1 and (task_hits >= 1 or object_hits >= 1):
        matched_terms = list(method_matched) + list(task_matched) + list(object_matched)
        if task_hits >= 1 and object_hits >= 1:
            matched_axis = "method_task" if task_hits >= object_hits else "method_object"
        elif task_hits >= 1:
            matched_axis = "method_task"
        else:
            matched_axis = "method_object"
    # Rule 1b: Re04-fix — method/task/object threshold-hit still counts
    # for eligibility, but tagged with `_threshold` suffix.
    elif (method_hits + len(method_threshold) >= 1) and (
        task_hits + len(task_threshold) >= 1
        or object_hits + len(object_threshold) >= 1
    ):
        matched_mode = "threshold"
        matched_terms = (
            list(method_matched) + list(method_threshold)
            + list(task_matched) + list(task_threshold)
            + list(object_matched) + list(object_threshold)
        )
        th_task = task_hits + len(task_threshold)
        th_obj = object_hits + len(object_threshold)
        if th_task >= 1 and th_obj >= 1:
            matched_axis = "method_task_threshold" if th_task >= th_obj else "method_object_threshold"
        elif th_task >= 1:
            matched_axis = "method_task_threshold"
        else:
            matched_axis = "method_object_threshold"
    # Rule 2: query_atoms_en ≥ 2 keyword-groups (strict or threshold)
    elif (len(atom_matched) + len(atom_threshold)) >= 2:
        matched_mode = "threshold" if atom_threshold and not atom_matched else "strict"
        matched_terms = list(atom_matched) + list(atom_threshold)
        matched_axis = "method_object"  # generic
        if matched_mode == "threshold":
            matched_axis = "method_object_threshold"
    # Rule 3: ER already core
    elif cid in _core_ids(reviews):
        matched_terms = list(method_matched) + list(task_matched) + list(object_matched)
        matched_axis = "method_task"
    else:
        matched_terms = []
        matched_axis = "none"
        rejected_reason = (
            f"no relevance match: method={method_hits}+th={len(method_threshold)} "
            f"task={task_hits}+th={len(task_threshold)} "
            f"object={object_hits}+th={len(object_threshold)} "
            f"atoms={len(atom_matched)}+th={len(atom_threshold)}"
        )

    return {
        "candidate_id": cid,
        "seed_eligible": matched_axis != "none",
        "matched_axis": matched_axis,
        "matched_mode": matched_mode,
        "matched_terms": matched_terms[:8],
        "rejected_reason": rejected_reason,
        "_debug": {
            "method_hits": method_hits,
            "method_threshold_hits": len(method_threshold),
            "task_hits": task_hits,
            "task_threshold_hits": len(task_threshold),
            "object_hits": object_hits,
            "object_threshold_hits": len(object_threshold),
            "atom_hits": len(atom_matched),
            "atom_threshold_hits": len(atom_threshold),
        },
    }


def filter_seeds(
    seeds: list[dict[str, Any]],
    parsed_topic: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a list of seed candidates into (eligible, rejected) with verdicts."""
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for s in seeds:
        v = evaluate_seed(candidate=s, parsed_topic=parsed_topic, reviews=reviews)
        v["_title"] = (s.get("title") or "")[:80]
        if v["seed_eligible"]:
            eligible.append(v)
        else:
            rejected.append(v)
    return eligible, rejected
