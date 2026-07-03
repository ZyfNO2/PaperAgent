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

Re04-fix SOP §5: the old _TOKEN_RE captured Chinese characters, so when
Round 1 crossref returned 8 中文 papers (Case 027), the expander built
queries like "基于YOLOv5 的 飞机 目标 检测" and sent them to English APIs,
getting back JATS noise. Now: detect Chinese-dominated tokens, skip them
when building queries, and if all queries would be Chinese-garbled, return
an explicit `degraded_reason` so the orchestrator can mark the round.

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


# Re04-fix SOP §5.A: split token regex into ASCII and CJK so we can
# route them separately. ASCII tokens go to English APIs; CJK tokens
# never should (per AutoResearchClaw's english-only query adapters).
_TOKEN_ASCII_RE = re.compile(r"[a-z0-9]{2,}")
_TOKEN_CJK_RE = re.compile(r"[一-鿿]{2,}")
_CHINESE_CHAR_RE = re.compile(r"[一-鿿]")


def _is_chinese_dominated(text: str, threshold: float = 0.5) -> bool:
    """Return True if >threshold of alphanumeric chars in `text` are CJK.

    A single CJK character between English words (e.g. "YOLOv5模型") is
    fine; what we want to catch is "基于YOLOv5模型" or pure Chinese strings.
    """
    if not text:
        return False
    alnum = [c for c in text if c.isalnum()]
    if not alnum:
        return False
    n_zh = sum(1 for c in alnum if _CHINESE_CHAR_RE.match(c))
    return (n_zh / len(alnum)) > threshold


def _filter_english_tokens(tokens: list[str]) -> list[str]:
    """Drop tokens that are Chinese-dominated so we don't feed garbled
    queries to English-only adapters (arxiv, openalex, crossref, s2)."""
    return [t for t in tokens if not _is_chinese_dominated(t)]


def _tokens(text: str) -> list[str]:
    """Tokenize; only ASCII alphanumeric (CJK handled separately)."""
    return [t.lower() for t in _TOKEN_ASCII_RE.findall(text or "") if t.lower() not in _STOPWORDS]


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
    """Return a list of {query, family, source_signal} for Round 2 fan-out.

    Re04-fix SOP §5: drop CJK-dominated tokens BEFORE building queries.
    If after filtering nothing usable remains, return a single-element
    list whose dict carries `degraded_reason: "all_queries_chinese_garbled_skipped"`
    so `re04_entry` can surface it in `round_delta`.
    """
    method_counter: Counter = Counter()
    object_counter: Counter = Counter()
    dataset_signals: list[str] = []
    repo_signals: list[str] = []

    for adapter in ("arxiv", "openalex", "crossref"):
        for item in r1_raw.get(adapter) or []:
            title = item.get("title") or ""
            abstract = item.get("abstract") or ""
            text = f"{title} {abstract}"
            # Re04-fix SOP §5.B: skip CJK-dominated tokens before counting.
            for tok in _filter_english_tokens(_tokens(text)):
                method_counter[tok] += 1
            for tok in _filter_english_tokens(_tokens(item.get("abstract") or "")):
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

    # Re04-fix SOP §5.B (second pass): skip the actual query strings
    # if they would be CJK-dominated. Build a list and filter post hoc.
    raw_out: list[dict[str, str]] = []
    for m in methods:
        for o in objects:
            q = _word_cap(f"{m} {o}", 6)
            if q:
                raw_out.append({"query": q, "family": "method_object", "source_signal": f"r1:{m}+{o}"})
    for m in methods:
        raw_out.append({"query": _word_cap(f"{m} benchmark", 6), "family": "benchmark", "source_signal": f"r1:{m} benchmark"})
        raw_out.append({"query": _word_cap(f"{m} survey", 6), "family": "survey", "source_signal": f"r1:{m} survey"})
    for ds in dataset_signals[:3]:
        raw_out.append({"query": _word_cap(f"{ds} dataset", 4), "family": "dataset", "source_signal": f"r1:dataset={ds}"})
    for repo in repo_signals[:3]:
        # Repos go to github (short query)
        raw_out.append({"query": _word_cap(repo, 4), "family": "repo", "source_signal": f"r1:repo={repo}"})

    # Deduplicate and filter out Chinese-garbled queries.
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for row in raw_out:
        q = row.get("query") or ""
        if not q or q in seen:
            continue
        if _is_chinese_dominated(q):
            # Skip silently — keep going to see if any English query survives.
            continue
        seen.add(q)
        deduped.append(row)

    # Re04-fix SOP §5.C: explicit degraded marker if nothing usable.
    if not deduped:
        return [{
            "query": "",
            "family": "method_object",
            "source_signal": "r1:none",
            "degraded_reason": "all_queries_chinese_garbled_skipped",
        }]
    return deduped
