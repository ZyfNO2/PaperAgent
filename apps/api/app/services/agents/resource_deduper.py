"""Re04 SOP §5 Task 5 — cross-source dedup + ranking for raw candidates.

Reference: AutoResearchClaw /researchclaw/literature/search.py
- DOI > arXiv ID > normalized title fallback for identity
- Merge provenance (sources / queries / rounds) when collapsing hits
- Rank by (relevance_tier, citation_count, year) — not raw score

Inputs: list of raw candidate dicts (mixed from arxiv / openalex /
crossref / semantic_scholar / github).

Output: list of merged candidate dicts in stable priority order, each
carrying:
- dedup_key (the key that won: "doi:..." / "arxiv:..." / "title:...")
- sources: list[str]   (where it was seen)
- queries: list[str]   (which queries produced it)
- rounds: list[int]    (which rounds)
- citation_count: int  (max across sources)

Acceptance (SOP §5 Task 5):
- Same paper from arxiv + openalex + semantic_scholar → 1 candidate
- Provenance list keeps all sources
- citation_count = max across sources (not sum)
- Off-topic high-citation papers cannot leapfrog a relevance gate;
  we expose a `apply_relevance_gate()` for the orchestrator to call
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

from ..retrieval._http import title_similarity

# Tier ordering: lower number = higher priority.
TIER_ORDER = {
    "core": 0,
    "candidate": 1,
    "long_tail": 2,
    "needs_manual": 3,
    "rejected": 4,
    "unknown": 5,
    "parallel": 1,
    "baseline": 1,
    "reference": 2,
    "module": 2,
    "dataset": 1,
    "repo": 1,
}

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE)
# Allow legacy arXiv ids (e.g. cs/0102034) when the paper_id is short
_ARXIV_LEGACY_RE = re.compile(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", re.IGNORECASE)


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi.strip().lower()
    if d.startswith("https://doi.org/"):
        d = d[len("https://doi.org/"):]
    if d.startswith("http://doi.org/"):
        d = d[len("http://doi.org/"):]
    if d.startswith("doi:"):
        d = d[4:]
    m = _DOI_RE.search(d)
    return f"doi:{m.group(0).lower()}" if m else None


def _norm_arxiv(arxiv_id: str | None, url: str | None) -> str | None:
    """Extract canonical arXiv id from explicit field or URL."""
    for src in (arxiv_id, url):
        if not src:
            continue
        m = _ARXIV_RE.search(src)
        if m:
            return f"arxiv:{m.group(1).lower()}"
        m2 = _ARXIV_LEGACY_RE.search(src)
        if m2:
            return f"arxiv:{m2.group(1).lower()}"
    return None


def _norm_title(title: str | None) -> str | None:
    """Title-key normalization. We use a conservative variant that does
    NOT strip common stopwords ("a", "the", "of"...) so that short
    titles like "A paper" still produce a non-empty key. The trade-off
    is higher collision risk on 1-2-word titles, which is acceptable
    because:
    1) DOI / arxiv keys always take priority;
    2) Title-keyed records go through the similarity sweep anyway.
    """
    if not title:
        return None
    t = title.lower()
    t = re.sub(r"[^a-z0-9一-鿿\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return f"title:{t}" if t else None


def dedup_key(cand: dict) -> str | None:
    """Compute the identity key for a candidate.

    Priority: DOI > arXiv ID > normalized title.
    Returns None if candidate has no usable identity.
    """
    doi = cand.get("doi")
    if isinstance(doi, list):
        doi = next((d for d in doi if d), None)
    k = _norm_doi(doi)
    if k:
        return k
    k = _norm_arxiv(cand.get("arxiv_id"), cand.get("url"))
    if k:
        return k
    return _norm_title(cand.get("title"))


def _coerce_int(x: Any) -> int:
    if isinstance(x, int):
        return x
    if isinstance(x, (str, float)):
        try:
            return int(x)
        except (ValueError, TypeError):
            return 0
    return 0


def _merge(a: dict, b: dict) -> dict:
    """Merge two candidate dicts with the same dedup key.

    Keeps the more complete record as base, but merges provenance +
    max citation_count + earliest year.
    """
    out = dict(a)
    # Provenance — pull from both 'sources' list and 'source' scalar.
    for source_field, target, scalar in (
        ("sources", "sources", "source"),
        ("source_queries", "queries", "source_query"),
        ("source_rounds", "rounds", "source_round"),
    ):
        merged: list[Any] = []
        for src in (a.get(target) or [], b.get(target) or []):
            if isinstance(src, list):
                merged.extend(src)
            elif src is not None:
                merged.append(src)
        # Also pick up the scalar from a and b if the target list is empty
        for record in (a, b):
            s = record.get(scalar)
            if s is not None and s not in merged:
                merged.append(s)
        if merged:
            # de-dup while preserving order
            seen = set()
            deduped: list[Any] = []
            for x in merged:
                if x in seen:
                    continue
                seen.add(x)
                deduped.append(x)
            out[target] = deduped

    # Identity: keep first non-empty DOI / arxiv_id / paper_id
    for f in ("doi", "arxiv_id", "paper_id"):
        if not out.get(f) and b.get(f):
            out[f] = b[f]

    # Text fields: longest wins (more complete)
    for f in ("title", "abstract", "venue"):
        a_v, b_v = a.get(f), b.get(f)
        if isinstance(a_v, str) and isinstance(b_v, str) and len(b_v) > len(a_v):
            out[f] = b_v

    # Numeric: keep max citation_count, max year
    a_cc, b_cc = _coerce_int(a.get("citation_count")), _coerce_int(b.get("citation_count"))
    out["citation_count"] = max(a_cc, b_cc)
    a_y, b_y = _coerce_int(a.get("year")), _coerce_int(b.get("year"))
    if a_y and b_y:
        out["year"] = max(a_y, b_y)
    elif b_y and not a_y:
        out["year"] = b_y

    # evidence_type stays as set
    if "evidence_type" in a and "evidence_type" in b and a["evidence_type"] != b["evidence_type"]:
        out["evidence_type"] = a["evidence_type"]  # first wins for the merged record
    return out


def dedup_candidates(cands: Iterable[dict], *, similarity_threshold: float = 0.85) -> list[dict]:
    """Group raw candidates by identity key (DOI > arxiv > title).

    For candidates with no key, fall back to a title-similarity sweep
    against the keyed groups; if no similar title exists, create a new
    group keyed on its normalized title.

    After the first pass, records that share a key (e.g. one record
    indexed by DOI but carrying the arxiv_id too) get unioned with the
    record that was indexed only by arxiv_id — so a single paper seen
    by arxiv-only + openalex (DOI) + s2 (DOI+arxiv) collapses to ONE
    merged record.

    Returns a list of merged candidates in input order of first
    appearance.
    """
    keyed: dict[str, dict] = {}        # key -> merged record
    key_to_keys: dict[str, set[str]] = {}  # key -> set of equivalent keys
    unkeyed: list[dict] = []           # candidates with no identity key
    order: list[str] = []              # first-appearance order of canonical keys

    def _ingest(c: dict) -> None:
        keys_here: set[str] = set()
        k = dedup_key(c)
        if k:
            keys_here.add(k)
        # Also derive alias keys from any other identity field present.
        # This is what allows an arxiv-only candidate to be unioned later
        # with a doi-keyed candidate for the same paper.
        a = _norm_arxiv(c.get("arxiv_id"), c.get("url"))
        if a and a not in keys_here:
            keys_here.add(a)
        d = _norm_doi(c.get("doi") if isinstance(c.get("doi"), str) else None)
        if d and d not in keys_here:
            keys_here.add(d)
        if not keys_here:
            unkeyed.append(c)
            return

        # Find the canonical key: any existing key in the group, else the
        # first one we saw.
        canonical = None
        for kk in keys_here:
            if kk in keyed:
                canonical = kk
                break
        if canonical is None:
            canonical = next(iter(keys_here))
        # Make sure all alias keys map to the canonical key.
        if canonical not in keyed:
            base = dict(c)
            base.setdefault("sources", [])
            base.setdefault("queries", [])
            base.setdefault("rounds", [])
            if c.get("source") and c["source"] not in base["sources"]:
                base["sources"].append(c["source"])
            if c.get("source_query") and c["source_query"] not in base["queries"]:
                base["queries"].append(c["source_query"])
            if c.get("source_round") is not None and c["source_round"] not in base["rounds"]:
                base["rounds"].append(c["source_round"])
            base["dedup_key"] = canonical
            base["citation_count"] = _coerce_int(c.get("citation_count"))
            keyed[canonical] = base
            order.append(canonical)
        else:
            keyed[canonical] = _merge(keyed[canonical], c)
        # Track that all keys_here map to canonical.
        for kk in keys_here:
            key_to_keys.setdefault(kk, set()).add(canonical)
            for alias in key_to_keys.get(kk, []):
                key_to_keys[canonical].add(alias)
                key_to_keys.setdefault(alias, set()).add(canonical)

    for c in cands:
        _ingest(c)

    # Second pass: if we discovered mid-stream that two keys are actually
    # the same paper (because a later record carries both identifiers),
    # union them. We do this by re-walking the order list and merging
    # any pair where one key's record carries the other's identity.
    def _records_share_identity(a: dict, b: dict) -> bool:
        if a.get("doi") and b.get("doi") and _norm_doi(a["doi"]) == _norm_doi(b["doi"]):
            return True
        if a.get("arxiv_id") and b.get("arxiv_id"):
            if _norm_arxiv(a["arxiv_id"], None) == _norm_arxiv(b["arxiv_id"], None):
                return True
        if a.get("arxiv_id") and (b.get("url") or "").startswith("http"):
            if _norm_arxiv(None, b["url"]) == _norm_arxiv(a["arxiv_id"], None):
                return True
        if b.get("arxiv_id") and (a.get("url") or "").startswith("http"):
            if _norm_arxiv(None, a["url"]) == _norm_arxiv(b["arxiv_id"], None):
                return True
        return False

    changed = True
    while changed:
        changed = False
        seen_canonicals: set[str] = set()
        new_order: list[str] = []
        for k in order:
            if k not in keyed:
                continue
            merged = False
            for prior in seen_canonicals:
                if _records_share_identity(keyed[prior], keyed[k]):
                    keyed[prior] = _merge(keyed[prior], keyed[k])
                    del keyed[k]
                    merged = True
                    changed = True
                    break
            if not merged:
                new_order.append(k)
                seen_canonicals.add(k)
        order = new_order

    # Promote the dedup_key to the highest-priority identifier across
    # the merged record: DOI > arxiv > title. So even if the candidate
    # was indexed by arxiv first, if it carries a DOI, the dedup_key
    # should reflect that.
    def _best_key(rec: dict) -> str:
        d = _norm_doi(rec.get("doi") if isinstance(rec.get("doi"), str) else None)
        if d:
            return d
        a = _norm_arxiv(rec.get("arxiv_id"), rec.get("url"))
        if a:
            return a
        t = _norm_title(rec.get("title"))
        if t:
            return t
        return rec.get("dedup_key", "title:anon")

    for k in list(keyed.keys()):
        rec = keyed[k]
        new_k = _best_key(rec)
        if new_k != k:
            # Remap. If new_k already exists, merge.
            if new_k in keyed and new_k != k:
                keyed[new_k] = _merge(keyed[new_k], rec)
                del keyed[k]
            else:
                rec["dedup_key"] = new_k
                keyed[new_k] = rec
                del keyed[k]

    # Re-derive order list from the (possibly remapped) keyed dict
    order = list(keyed.keys())
    # by title similarity; otherwise create a title-keyed group.
    for c in unkeyed:
        title = c.get("title") or ""
        best_key: str | None = None
        best_sim: float = 0.0
        for k in order:
            sim = title_similarity(title, keyed[k].get("title") or "")
            if sim > best_sim:
                best_sim = sim
                best_key = k
        if best_key and best_sim >= similarity_threshold:
            keyed[best_key] = _merge(keyed[best_key], c)
        else:
            tk = _norm_title(title) or f"title:anon-{len(keyed)}"
            base = dict(c)
            base.setdefault("sources", [])
            base.setdefault("queries", [])
            base.setdefault("rounds", [])
            if c.get("source") and c["source"] not in base["sources"]:
                base["sources"].append(c["source"])
            base["dedup_key"] = tk
            base["citation_count"] = _coerce_int(c.get("citation_count"))
            keyed[tk] = base
            order.append(tk)

    return [keyed[k] for k in order]


def _tier_rank(cand: dict) -> int:
    tier = cand.get("role_hint") or cand.get("tier") or cand.get("evidence_type") or "unknown"
    return TIER_ORDER.get(tier, 5)


def rank_candidates(
    cands: list[dict],
    *,
    gate_tier: str | None = None,
    role_hint: str | None = None,
) -> list[dict]:
    """Sort by (tier_rank asc, citation_count desc, year desc, title asc).

    If `gate_tier` is set, candidates whose role_hint / tier is worse
    than the gate are pushed to the end (NOT removed — the orchestrator
    can decide). This is the SOP §5 Task 5 acceptance: "off-topic
    high-citation papers cannot leapfrog a relevance gate".
    """
    gate_rank = TIER_ORDER.get(gate_tier, 0) if gate_tier else None

    def sort_key(c: dict):
        tr = _tier_rank(c)
        gated_out = 0 if (gate_rank is None or tr <= gate_rank) else 1
        # For ties on tier, prefer newer year first, then more citations.
        # Re04 SOP §1.2: "不要单纯按分数" — year matters, citation only
        # breaks ties inside the same year.
        return (
            gated_out,                # in-gate first
            tr,                       # tighter tier first
            -_coerce_int(c.get("year")),            # newer year first
            -_coerce_int(c.get("citation_count")),  # higher citations break ties
            (c.get("title") or "").lower(),
        )

    return sorted(cands, key=sort_key)


def apply_relevance_gate(cands: list[dict], min_tier: str = "rejected") -> list[dict]:
    """Hard filter: drop candidates with tier worse than `min_tier`.

    'rejected' means nothing is dropped. 'candidate' means drop
    long_tail + needs_manual + rejected. 'core' means keep only core.
    """
    cap = TIER_ORDER.get(min_tier, 5)
    return [c for c in cands if _tier_rank(c) <= cap]


def group_by_provenance(cands: list[dict]) -> dict[str, int]:
    """Count candidates by source for SourceLedger / eval reporting."""
    out: dict[str, int] = defaultdict(int)
    for c in cands:
        for s in c.get("sources") or [c.get("source") or "unknown"]:
            out[s] += 1
    return dict(out)
