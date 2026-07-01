"""Session 47: Chunk-level reranker (SOP §7 + §11 Task 5).

5 因子加权:
  keyword_match  0.35  query 关键词在 chunk 的命中率
  section_type   0.25  method/experiment > abstract > reference
  recency        0.15  paper year 越新越高
  rerank_score   0.15  沿用原 fused score (传入)
  type_coverage  0.10  多类型 chunk 加权 (少数类型加分)

输入: chunks_with_scores: [(chunk_meta_dict, fused_score)]
      query: str
      paper_year_lookup: {paper_id: year}

输出: list[(chunk_meta_dict, final_score)]  按 final_score 降序
"""

from __future__ import annotations

from datetime import datetime, timezone

# 因子权重
W_KEYWORD_MATCH = 0.35
W_SECTION_TYPE = 0.25
W_RECENCY = 0.15
W_RERANK_SCORE = 0.15
W_TYPE_COVERAGE = 0.10

# 章节类型权重 (rank)
_SECTION_TYPE_SCORE = {
    "method": 1.0,
    "experiment": 1.0,
    "result": 0.9,
    "conclusion": 0.8,
    "abstract": 0.7,
    "introduction": 0.5,
    "related_work": 0.4,
    "limitation": 0.5,
    "title": 0.4,
    "unknown": 0.3,
}


def _keyword_match_score(query: str, text: str) -> float:
    """query 中 keyword 命中率 (基于 token overlap, 不重新调 rewrite_query)."""

    if not query or not text:
        return 0.0
    from . import embedding

    q_tokens = set(embedding.tokenize(query))
    t_tokens = set(embedding.tokenize(text))
    if not q_tokens or not t_tokens:
        return 0.0
    overlap = q_tokens & t_tokens
    return len(overlap) / len(q_tokens)


def _section_type_score(chunk_type: str) -> float:
    return _SECTION_TYPE_SCORE.get(chunk_type or "unknown", 0.3)


def _recency_score(year: int | None) -> float:
    """year 越近越高, 范围 [0.3, 1.0]."""

    if not year:
        return 0.5
    cur = datetime.now(timezone.utc).year
    delta = max(0, cur - year)
    return max(0.3, 1.0 - delta * 0.05)


def rerank_chunks(
    query: str,
    chunks_with_scores: list[tuple[dict, float]],
    paper_year_lookup: dict[str, int | None] | None = None,
) -> list[tuple[dict, float]]:
    """多因子 chunk reranker.

    Args:
        query: 用户问题
        chunks_with_scores: [(chunk_meta, fused_score)]
        paper_year_lookup: {paper_id: year} 用于 recency 计算
    """

    if not chunks_with_scores:
        return []

    paper_year_lookup = paper_year_lookup or {}

    # type_coverage: 统计 chunk_type 分布
    type_counts: dict[str, int] = {}
    for meta, _ in chunks_with_scores:
        ct = meta.get("chunk_type", "unknown") or "unknown"
        type_counts[ct] = type_counts.get(ct, 0) + 1
    total = sum(type_counts.values()) or 1

    out: list[tuple[dict, float]] = []
    for meta, fused_score in chunks_with_scores:
        text = meta.get("text", "") or ""
        chunk_type = meta.get("chunk_type", "unknown") or "unknown"
        paper_id = meta.get("paper_id", "")

        kw_s = _keyword_match_score(query, text)
        sec_s = _section_type_score(chunk_type)
        rec_s = _recency_score(paper_year_lookup.get(paper_id))
        rerank_s = min(1.0, max(0.0, fused_score))  # 来自 RRF 的 fused_score 一般 < 0.05, 归一化
        # 简单归一化: 假设 fused_score 范围 [0, 0.05] → 映射到 [0, 1]
        rerank_norm = min(1.0, rerank_s * 20.0)
        # type coverage: 少数类型加分 (1.0 - share)
        type_share = type_counts.get(chunk_type, 0) / total
        type_s = 1.0 - type_share

        final = (
            W_KEYWORD_MATCH * kw_s
            + W_SECTION_TYPE * sec_s
            + W_RECENCY * rec_s
            + W_RERANK_SCORE * rerank_norm
            + W_TYPE_COVERAGE * type_s
        )

        # 写回 meta (供 paper_qa 读 rerank_score)
        meta_copy = dict(meta)
        meta_copy["rerank_score"] = round(final, 4)
        meta_copy["kw_score"] = round(kw_s, 4)
        meta_copy["section_score"] = round(sec_s, 4)
        meta_copy["recency_score"] = round(rec_s, 4)
        meta_copy["type_score"] = round(type_s, 4)
        out.append((meta_copy, round(final, 4)))

    out.sort(key=lambda x: x[1], reverse=True)
    return out


__all__ = [
    "W_KEYWORD_MATCH",
    "W_RECENCY",
    "W_RERANK_SCORE",
    "W_SECTION_TYPE",
    "W_TYPE_COVERAGE",
    "rerank_chunks",
]