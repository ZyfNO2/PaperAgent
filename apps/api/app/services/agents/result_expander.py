"""result_expander — Re03 SOP §3 Round 2: dynamic expansion from Round 1 hits.

Inputs:
  r1_raw    — Round 1 raw tool output (dict[adapter] -> list[items])
  pool      — CandidatePool with Round 1 candidates already merged

Output:
  list of (query_text, query_family) tuples that the orchestrator can
  fan out in Round 2.

Rules (Re03 SOP §1.6 / §3.2):
  - DO NOT blindly add `survey / benchmark / recent advances` suffix.
  - DO use the titles and abstracts from R1 hits to extract:
      * high-freq method tokens (e.g. "U-Net", "Transformer", "PointNet")
      * high-freq object tokens (e.g. "steel", "bridge", "Sentinel-2")
      * dataset names (e.g. "DTU", "ETH3D", "NEU-DET")
      * github repo full_names (for Round 3 dataset/repo search)
  - Each query MUST be ≤ 6 words for arxiv/openalex/crossref, ≤ 4 for github.

Ponytail: ~120 lines, no LLM, no network. Pure term extraction +
cartesian product with small caps.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


_STOPWORDS = {
    "a", "an", "the", "of", "for", "in", "on", "and", "or", "with",
    "to", "by", "from", "its", "is", "are", "was", "be", "as", "at",
    "via", "using", "based", "study", "analysis", "empirical",
    "towards", "toward", "into", "exploring", "comparison", "tasks",
    "effectiveness", "investigation", "comprehensive", "novel",
    "challenge", "challenges", "gaps", "gap", "critical", "survey", "review",
}

_TOKEN_RE = re.compile(r"[a-z0-9一-鿿]{2,}")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def _top_k(counter: Counter, k: int) -> list[str]:
    return [w for w, _ in counter.most_common(k)]


def _word_cap(q: str, n: int) -> str:
    w = q.split()
    return " ".join(w[:n]) if len(w) > n else q


def expand_from_round1(
    r1_raw: dict[str, list[dict[str, Any]]],
    *,
    parsed_topic: dict[str, Any] | None = None,
    top_method_k: int = 4,
    top_object_k: int = 4,
) -> list[dict[str, str]]:
    """Return a list of {query, family, source_signal} for Round 2 fan-out."""
    method_counter: Counter = Counter()
    object_counter: Counter = Counter()
    dataset_signals: list[str] = []
    repo_signals: list[str] = []

    for adapter in ("arxiv", "openalex", "crossref"):
        for item in r1_raw.get(adapter) or []:
            title = item.get("title") or ""
            abstract = item.get("abstract") or ""
            text = f"{title} {abstract}"
            for tok in _tokens(text):
                method_counter[tok] += 1
            for tok in _tokens(item.get("abstract") or ""):
                object_counter[tok] += 1
            # Capture dataset-name-like signals (short uppercase phrases)
            for m in re.findall(r"\b[A-Z][A-Za-z0-9\-]{2,}\b", title):
                if m.upper() == m and len(m) >= 3:
                    dataset_signals.append(m)
    for item in r1_raw.get("github") or []:
        nm = (item.get("full_name") or item.get("name") or "").strip()
        if nm:
            repo_signals.append(nm)

    # Reuse the topic's known method/object_terms as anchors (so we don't
    # hallucinate new methods just because Round 1 had noisy token counts).
    method_anchors = set((parsed_topic or {}).get("method_terms") or [])
    object_anchors = set((parsed_topic or {}).get("object_terms") or [])

    # Filter top tokens against anchors
    methods = [m for m in _top_k(method_counter, 30) if m in {x.lower() for x in method_anchors}][:top_method_k]
    if not methods:
        methods = _top_k(method_counter, top_method_k)
    objects = [o for o in _top_k(object_counter, 30) if o in {x.lower() for x in object_anchors}][:top_object_k]
    if not objects:
        objects = _top_k(object_counter, top_object_k)

    out: list[dict[str, str]] = []
    for m in methods:
        for o in objects:
            q = _word_cap(f"{m} {o}", 6)
            if q:
                out.append({"query": q, "family": "method_object", "source_signal": f"r1:{m}+{o}"})
    for m in methods:
        out.append({"query": _word_cap(f"{m} benchmark", 6), "family": "benchmark", "source_signal": f"r1:{m} benchmark"})
        out.append({"query": _word_cap(f"{m} survey", 6), "family": "survey", "source_signal": f"r1:{m} survey"})
    for ds in dataset_signals[:3]:
        out.append({"query": _word_cap(f"{ds} dataset", 4), "family": "dataset", "source_signal": f"r1:dataset={ds}"})
    for repo in repo_signals[:3]:
        # Repos go to github (short query)
        out.append({"query": _word_cap(repo, 4), "family": "repo", "source_signal": f"r1:repo={repo}"})

    # Deduplicate
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for row in out:
        if row["query"] not in seen:
            seen.add(row["query"])
            deduped.append(row)
    return deduped
