"""Re10 SearchReflectionLoop helpers — plan/observation shapes.

ponytail: split out of search_reflection_loop.py so the orchestrator
itself stays close to the 350-line mark.  Pure data-shaping; no LLM,
no adapters.
"""
from __future__ import annotations

import re
import time
from typing import Any


def norm_title(t: Any) -> str:
    """Lowercase + collapse-whitespace title used for dedup."""
    return re.sub(r"\s+", " ", (str(t or "").strip()).lower())


def candidate_key(c: dict) -> str:
    """Stable dedup key: arxiv_id → doi → normalized title → url."""
    arxiv = c.get("arxiv_id") or c.get("arxiv")
    if arxiv:
        return f"arxiv:{arxiv}"
    doi = c.get("doi")
    if doi:
        return f"doi:{str(doi).lower()}"
    title = norm_title(c.get("title"))
    if title:
        return f"t:{title}"
    return f"url:{c.get('url') or ''}"


def ensure_source_run(c: dict, source: str) -> dict:
    """Stamp source_run on a candidate (SOP §9.5)."""
    c2 = dict(c)
    c2.setdefault("source_run", source)
    return c2


def has_placeholder(q: str) -> bool:
    """Detect unsubstituted ``{...}`` or bare ``X``."""
    return bool(re.search(r"[{}]|\bX\b", q or ""))


def bucket_for_tool(tool: str, hit: dict) -> str:
    """Map a tool+hit pair to a candidate bucket (paper / dataset / repo)."""
    t = (hit.get("evidence_type") or hit.get("type") or "").lower()
    if tool == "github" or "github.com" in (hit.get("url") or "").lower():
        return "repo"
    if t in {"dataset", "datasets"} or tool == "huggingface":
        return "dataset"
    return "paper"


def _en_queries_only(queries: list[str], domain_kws: dict) -> list[str]:
    """Drop queries that contain Chinese chars (non-Latin script).

    DomainScout must produce English queries; if it returns Chinese
    fragments (e.g. ``"钢材裂缝分割 dataset benchmark"``) we discard
    them rather than feeding them to arxiv/openalex/github which reject
    or distort them.  ponytail: filter at the helper boundary so the
    loop never sees a CJK query.
    """
    cjk = re.compile(r"[一-鿿]")
    en: list[str] = []
    for q in queries or []:
        q = (q or "").strip()
        if not q or cjk.search(q):
            continue
        en.append(q)
    # Fall back to domain_kws.en[0] derived probes if everything was
    # Chinese (LLM bilingual parsing often produces a mixed bag).
    if not en:
        en_kws = (domain_kws or {}).get("en") or []
        first = next((k for k in en_kws if k and not cjk.search(str(k))), "")
        if first:
            en = [f"{first} dataset benchmark", f"{first} baseline method"]
    return en


def _en_first_atom(domain_kws: dict) -> str:
    """First English-only atom from ``domain_keywords.en``, skipping CJK."""
    cjk = re.compile(r"[一-鿿]")
    for k in (domain_kws or {}).get("en") or []:
        if k and not cjk.search(str(k)):
            return str(k).strip()
    return ""


def build_round_plan(
    domain_kws: dict, history: dict, must_search: list[str],
) -> list[dict]:
    """Build the search plan for the upcoming round.

    Rule layer: take ``must_search`` from DomainScout, bind adapter +
    target_role, drop anything that overlaps with ``avoid_search`` or
    contains CJK characters (arxiv/openalex/github reject CJK tokens).
    Adds one dataset probe + one repo probe if neither is present, both
    built from the first English-only atom (NOT a hardcoded template
    fallback).
    """
    plan: list[dict] = []
    avoid = set(history.get("avoid_search") or [])
    clean_must = _en_queries_only(must_search or [], domain_kws)

    for raw_q in clean_must[:4]:
        q = raw_q.strip()
        if not q:
            continue
        if any(bad.lower() in q.lower() for bad in avoid):
            continue
        if "github" in q or "implementation" in q or "code" in q:
            tool, role = "github", "repo"
        elif "dataset" in q or "benchmark" in q or "corpus" in q:
            tool, role = "openalex", "dataset"
        elif "baseline" in q:
            tool, role = "openalex", "baseline"
        else:
            tool, role = "arxiv", "core_paper"
        plan.append({
            "query": q,
            "tool": tool,
            "target_role": role,
            "why": f"must_search from DomainScout ({q})",
            "expected_signal": "title" if role != "repo" else "repo_readme",
        })

    first_en = _en_first_atom(domain_kws)
    if first_en and not any(p.get("target_role") == "dataset" for p in plan):
        probe = f"{first_en} dataset benchmark"
        if not any(bad.lower() in probe.lower() for bad in avoid):
            plan.append({
                "query": probe,
                "tool": "openalex",
                "target_role": "dataset",
                "why": f"fallback dataset probe from atom {first_en!r}",
                "expected_signal": "dataset_name",
            })
    # Repo probe must be the first English-only atom + repo-relevant
    # suffix.  NO hardcoded UNet/CV template.  Falls back to a domain-
    # routed suffix to keep the probe in-bounds.
    if first_en and not any(p.get("target_role") == "repo" for p in plan):
        probe = f"{first_en} open source"
        if not any(bad.lower() in probe.lower() for bad in avoid):
            plan.append({
                "query": probe,
                "tool": "github",
                "target_role": "repo",
                "why": f"fallback repo probe from atom {first_en!r}",
                "expected_signal": "repo_readme",
            })

    return plan


def build_observations(
    plan: list[dict],
    tool_results: list[dict],
    accepted: list[dict],
    rejected: list[dict],
    placeholder_leaks: list[str],
    failed_queries: list[dict],
    url_repair_n: int,
    round_num: int,
) -> dict:
    """Assemble the round's observations dict for the critic."""
    noise = [c.get("title") for c in rejected if c.get("title")][:5]
    empty_url = [
        c.get("title") for c in accepted
        if not (c.get("url") or c.get("arxiv_id") or c.get("doi"))
    ][:5]
    has_dataset = any(c.get("_bucket") == "dataset" for c in accepted)
    has_baseline = any(
        c.get("_bucket") == "paper" and "baseline" in (c.get("role") or "")
        for c in accepted
    )
    has_repo = any(c.get("_bucket") == "repo" for c in accepted)
    return {
        "round": round_num,
        "executed_queries": plan,
        "tool_results": tool_results,
        "good_candidates": [c.get("title") for c in accepted if c.get("title")][:5],
        "noise_candidates": noise,
        "empty_url_candidates": empty_url,
        "empty_query_results": [
            q["query"] for q in failed_queries if q.get("error") == "empty result"
        ],
        "dataset_gap": not has_dataset,
        "baseline_gap": not has_baseline,
        "repo_gap": not has_repo,
        "query_placeholder_leaks": placeholder_leaks,
        "useful_terms_discovered": [],
        "url_repair_n": url_repair_n,
        "failed_queries": failed_queries,
    }


__all__ = [
    "norm_title",
    "candidate_key",
    "ensure_source_run",
    "has_placeholder",
    "bucket_for_tool",
    "build_round_plan",
    "build_observations",
]
