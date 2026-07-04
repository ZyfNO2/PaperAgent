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


def _en_queries_only(queries: list[str], domain_kws: dict) -> tuple[list[str], bool]:
    """Drop queries that contain Chinese chars (non-Latin script).

    DomainScout must produce English queries; if it returns Chinese
    fragments (e.g. ``"钢材裂缝分割 dataset benchmark"``) we discard
    them rather than feeding them to arxiv/openalex/github which reject
    or distort them.  ponytail: filter at the helper boundary so the
    loop never sees a CJK query.

    Returns ``(queries, is_fallback)`` where ``is_fallback`` is True
    when all input queries were CJK and we synthesized fallback probes
    from domain_kws.
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
    # FIX-4: do NOT put "[Fallback]" prefix in query text — the tag
    # belongs in structured metadata, not in the search string.
    if not en:
        en_kws = (domain_kws or {}).get("en") or []
        first = next((k for k in en_kws if k and not cjk.search(str(k))), "")
        if first:
            return [f"{first} dataset benchmark", f"{first} baseline method"], True
        return [], True
    return en, False


def flatten_axis_terms(topic_atoms: dict, axis: str) -> list[str]:
    """Flatten topic_atoms[axis] into a flat list of English-only term strings.

    Re-added for Re1.1 after being dropped during upstream churn. Accepts
    legacy shapes used throughout the code base — per-axis lists of strings,
    or lists of dicts with ``en``/``zh`` subkeys. Drops CJK-only entries
    and deduplicates case-insensitively.
    """
    cjk = re.compile(r"[一-鿿]")
    out: list[str] = []
    seen: set[str] = set()
    for raw in (topic_atoms.get(axis) or []):
        cand: list[str] = []
        if isinstance(raw, dict):
            en = str(raw.get("en") or "").strip()
            if en:
                cand.append(en)
        elif raw:
            cand.append(str(raw).strip())
        for t in cand:
            if not t or cjk.search(t):
                continue
            low = t.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(t)
    return out


def _en_first_atom(domain_kws: dict) -> str:
    """First English-only atom from ``domain_keywords.en``, skipping CJK."""
    cjk = re.compile(r"[一-鿿]")
    for k in (domain_kws or {}).get("en") or []:
        if k and not cjk.search(str(k)):
            return str(k).strip()
    return ""


def build_axis_bound_queries(domain_kws: dict, role: str) -> list[str]:
    """Build a small list of English-only search queries for a target role.

    Reconstructed for Re1.1 after being dropped from this module during
    upstream churn. Builds 2-4 targeted queries from the method/object/task
    /dataset keyword axes in ``domain_kws``. All queries are English-only
    (CJK-filtered) so they are safe for arxiv / openalex / crossref / github.

    Role semantics (mirrors the legacy ``role_queries`` block in
    ``search_reflection_loop``):
      - dataset:  method+object + "dataset benchmark" probes
      - repo:     method+object + "github official implementation" probes
      - baseline: method+object baseline/method paper probes
      - core_paper: top method+object "survey OR comparison" probes
    """
    cjk = re.compile(r"[一-鿿]")
    en = [str(k).strip() for k in (domain_kws.get("en") or []) if k and not cjk.search(str(k))]
    method = [str(k).strip() for k in (domain_kws.get("method") or []) if k and not cjk.search(str(k))]
    obj = [str(k).strip() for k in (domain_kws.get("object") or []) if k and not cjk.search(str(k))]
    ds = [str(k).strip() for k in (domain_kws.get("dataset_terms") or []) if k and not cjk.search(str(k))]

    head = (en or method or obj)[:3]
    m = method[:2]
    o = obj[:2]

    def q(*parts: str) -> str | None:
        joined = " ".join(p for p in parts if p).strip()
        return joined if joined and not cjk.search(joined) else None

    out: list[str] = []
    seen: set[str] = set()
    candidates: list[str | None] = []

    role_lower = (role or "").lower()
    if role_lower == "dataset":
        base_terms = ds[:2] or m[:1] + o[:1] or head[:1]
        for t in base_terms:
            candidates.append(q(t, "dataset benchmark"))
            candidates.append(q(t, "public dataset download"))
        candidates.append(q(head[0] if head else "", "dataset"))
    elif role_lower == "repo":
        for t in (m[:1] + o[:1] or head[:1]):
            candidates.append(q(t, "github official implementation"))
            candidates.append(q(t, "github code repository"))
        candidates.append(q(head[0] if head else "", "project page"))
    elif role_lower == "baseline":
        for t in (m[:1] + o[:1] or head[:1]):
            candidates.append(q(t, "baseline method"))
            candidates.append(q(t, "state of the art comparison"))
        candidates.append(q(head[0] if head else "", "review survey"))
    elif role_lower == "core_paper":
        for t in (m[:1] + o[:1] or head[:1]):
            candidates.append(q(t, "deep learning survey"))
            candidates.append(q(t, "benchmark comparison"))
        candidates.append(q(head[0] if head else "", "systematic review"))
    else:
        # Unknown role: fall back to plain English subset.
        candidates.extend(q(h) for h in head)

    for c in candidates:
        if c is None:
            continue
        low = c.lower()
        if low in seen or len(c) < 4:
            continue
        seen.add(low)
        out.append(c)
    return out[:6]


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
    clean_must, must_is_fallback = _en_queries_only(must_search or [], domain_kws)

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
        entry = {
            "query": q,
            "tool": tool,
            "target_role": role,
            "why": f"must_search from DomainScout ({q})",
            "expected_signal": "title" if role != "repo" else "repo_readme",
        }
        # FIX-4 P1-2: tag fallback queries in structured metadata
        if must_is_fallback:
            entry["fallback"] = True
            entry["fallback_reason"] = "llm_parse_failed"
            entry["why"] = f"[Fallback] {entry['why']}"
        plan.append(entry)

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
                "fallback": True,
                "fallback_reason": "axis_bound_fallback",
            })
    if first_en and not any(p.get("target_role") == "repo" for p in plan):
        probe = f"{first_en} open source"
        if not any(bad.lower() in probe.lower() for bad in avoid):
            plan.append({
                "query": probe,
                "tool": "github",
                "target_role": "repo",
                "why": f"fallback repo probe from atom {first_en!r}",
                "expected_signal": "repo_readme",
                "fallback": True,
                "fallback_reason": "axis_bound_fallback",
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
