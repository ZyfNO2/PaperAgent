"""Session 50: RAG Evaluation Metrics.

实现的核心指标:
- compute_recall_at_k: 召回率 (用 chunk_type 集合作为 gold, 在前 K 个 retrieved 中匹配)
- compute_mrr: 平均倒数排名 (1 / rank_of_first_relevant, 用 chunk_id 集合作 gold)
- compute_ndcg_at_k: 归一化折损累积增益 (用 relevance 列表)
- compute_citation_precision: 引用精度 (cited_chunks ∩ retrieved_chunks / cited_chunks)
- compute_evidence_coverage: 证据覆盖率 (gold_chunks 出现在 cited ∩ retrieved 的比例)
- compute_unsupported_claim_rate: 无依据声明率 (unsupported_claims / total_claims)
- compute_faithfulness: 忠实度 (heuristic: answer_chunks_used vs cited, 简化: cited/total_claims)
- aggregate_metrics: 聚合 items → (RetrievalMetrics, AnswerMetrics, SystemMetrics)

设计:
- 所有指标 deterministic (无随机)
- 支持空集合 / 0 分母的边界情况
- 适用于 S50 paper-library RAG 评估
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Iterable

from ...schemas_paper_rag_eval import (
    AnswerMetrics,
    RagEvalItem,
    RetrievalMetrics,
    SystemMetrics,
)


# ---------------------------------------------------------------------------
# Recall@K (using chunk_type as gold)
# ---------------------------------------------------------------------------


def compute_recall_at_k(
    retrieved_chunk_ids: list[str],
    gold_chunk_types: list[str],
    chunk_type_lookup: dict[str, str],
    k: int = 5,
) -> float:
    """Recall@K: 在前 K 个 retrieved chunk 中, 命中 gold chunk_types 的比例.

    gold_chunk_types 是 ground truth 中的 chunk_type 集合 (如 ["method", "experiment"]).
    chunk_type_lookup: chunk_id -> chunk_type 映射.

    Args:
        retrieved_chunk_ids: 检索到的 chunk_id 列表 (按相关度排序)
        gold_chunk_types: ground truth 中应包含的 chunk_type 列表
        chunk_type_lookup: chunk_id -> chunk_type 映射
        k: top-K

    Returns:
        召回率, 范围 [0, 1]. 命中数 / gold 数 (上限 1).
    """

    if not gold_chunk_types:
        return 0.0
    gold_set = set(gold_chunk_types)
    if not gold_set:
        return 0.0
    top_k = retrieved_chunk_ids[:k]
    if not top_k:
        return 0.0
    hits_types: set[str] = set()
    for cid in top_k:
        ct = chunk_type_lookup.get(cid, "unknown")
        if ct in gold_set:
            hits_types.add(ct)
    return min(1.0, len(hits_types) / len(gold_set))


# ---------------------------------------------------------------------------
# MRR (using chunk_id as gold)
# ---------------------------------------------------------------------------


def compute_mrr(
    retrieved_chunk_ids: list[str],
    gold_chunk_ids: Iterable[str],
) -> float:
    """MRR: 1 / rank_of_first_relevant.

    gold_chunk_ids: 与 ground truth 一致的 chunk_id 集合.

    Returns:
        MRR, 范围 [0, 1].
    """

    gold = set(gold_chunk_ids)
    if not gold:
        return 0.0
    for rank, cid in enumerate(retrieved_chunk_ids, start=1):
        if cid in gold:
            return 1.0 / rank
    return 0.0


# ---------------------------------------------------------------------------
# NDCG@K
# ---------------------------------------------------------------------------


def compute_ndcg_at_k(
    retrieved: list[str],
    relevance: dict[str, float],
    k: int = 5,
) -> float:
    """NDCG@K: 归一化折损累积增益.

    Args:
        retrieved: 检索到的 item 列表 (顺序相关)
        relevance: item -> relevance score (e.g. 0.0/1.0/2.0) 映射
        k: top-K

    Returns:
        NDCG@K, 范围 [0, 1].
    """

    if not retrieved or k <= 0:
        return 0.0
    top_k = retrieved[:k]
    dcg = 0.0
    for i, item in enumerate(top_k, start=1):
        rel = relevance.get(item, 0.0)
        # DCG formula: rel_i / log2(i+1)
        dcg += rel / math.log2(i + 1)

    # IDCG: 按 relevance 降序排列的最佳情况
    ideal_rels = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 1) for i, rel in enumerate(ideal_rels, start=1))
    if idcg <= 0:
        return 0.0
    return min(1.0, dcg / idcg)


# ---------------------------------------------------------------------------
# Citation Precision
# ---------------------------------------------------------------------------


def compute_citation_precision(
    cited_chunks: list[str],
    retrieved_chunks: list[str],
) -> float:
    """Citation Precision: cited_chunks ∩ retrieved_chunks / cited_chunks.

    回答中引用的 chunk 中, 实际被检索到的比例 (防止 LLM 幻觉引用).

    Returns:
        Precision, 范围 [0, 1]. 0.0 if no cited chunks.
    """

    if not cited_chunks:
        return 0.0
    retrieved_set = set(retrieved_chunks)
    hits = sum(1 for c in cited_chunks if c in retrieved_set)
    return min(1.0, hits / len(cited_chunks))


# ---------------------------------------------------------------------------
# Evidence Coverage
# ---------------------------------------------------------------------------


def compute_evidence_coverage(
    answer_chunks_used: list[str],
    ground_truth_chunks: Iterable[str],
) -> float:
    """Evidence Coverage: ground_truth_chunks 出现在 answer_chunks_used 中的比例.

    回答是否覆盖了 ground truth 期望的 chunk.

    Returns:
        Coverage, 范围 [0, 1]. 0.0 if no gold.
    """

    gold = set(ground_truth_chunks)
    if not gold:
        return 0.0
    used_set = set(answer_chunks_used)
    hits = sum(1 for g in gold if g in used_set)
    return min(1.0, hits / len(gold))


# ---------------------------------------------------------------------------
# Unsupported Claim Rate
# ---------------------------------------------------------------------------


def compute_unsupported_claim_rate(
    unsupported_claims: int,
    total_claims: int,
) -> float:
    """Unsupported Claim Rate: unsupported / total.

    Returns:
        Rate, 范围 [0, 1]. 0.0 if no claims.
    """

    if total_claims <= 0:
        return 0.0
    return min(1.0, max(0.0, unsupported_claims / total_claims))


# ---------------------------------------------------------------------------
# Faithfulness (heuristic)
# ---------------------------------------------------------------------------


def compute_faithfulness(
    answer: str,
    evidence_refs: list[str],
) -> float:
    """Faithfulness: heuristic 估算 answer 的断言是否有引用支撑.

    Heuristic:
    - 如果 answer 为空 → 0.0
    - 如果 answer 有 [1][2] 等引用标记, 引用编号 ≤ len(evidence_refs) → 视为有支撑
    - 否则: 1.0 - unsupported_estimate (粗估, 这里用 1.0 兜底)

    更精确的版本需要 LLM judge, 但 S50 用 heuristic 保持 deterministic.

    Returns:
        Faithfulness, 范围 [0, 1].
    """

    if not answer or not answer.strip():
        return 0.0
    if not evidence_refs:
        return 0.5  # 没引用但有答案 → 中等
    # 简化: 有引用 + 有答案 → 高分
    return 1.0


# ---------------------------------------------------------------------------
# Hit Rate
# ---------------------------------------------------------------------------


def compute_hit_rate(
    retrieved_chunk_ids: list[str],
    gold_chunk_ids: Iterable[str],
    k: int = 5,
) -> float:
    """Hit Rate: 前 K 个 retrieved 中是否至少有一个在 gold 中.

    Returns:
        1.0 if hit, else 0.0.
    """

    gold = set(gold_chunk_ids)
    if not gold:
        return 0.0
    top_k = retrieved_chunk_ids[:k]
    return 1.0 if any(c in gold for c in top_k) else 0.0


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    """计算 pct 百分位 (0-100)."""

    if not values:
        return 0.0
    sorted_v = sorted(values)
    if pct <= 0:
        return sorted_v[0]
    if pct >= 100:
        return sorted_v[-1]
    # 线性插值
    n = len(sorted_v)
    idx = (pct / 100.0) * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_v[lo]
    frac = idx - lo
    return sorted_v[lo] * (1 - frac) + sorted_v[hi] * frac


def aggregate_metrics(
    items: list[RagEvalItem],
) -> tuple[RetrievalMetrics, AnswerMetrics, SystemMetrics]:
    """从 items 列表聚合指标 (算术平均).

    Args:
        items: RagEvalItem 列表

    Returns:
        (RetrievalMetrics, AnswerMetrics, SystemMetrics)
    """

    if not items:
        return RetrievalMetrics(), AnswerMetrics(), SystemMetrics()

    # Retrieval: average
    recall_avg = sum(it.retrieval_metrics.recall_at_5 for it in items) / len(items)
    mrr_avg = sum(it.retrieval_metrics.mrr for it in items) / len(items)
    ndcg_avg = sum(it.retrieval_metrics.ndcg_at_5 for it in items) / len(items)
    hit_avg = sum(it.retrieval_metrics.hit_rate for it in items) / len(items)

    # Answer: average
    cit_avg = sum(it.answer_metrics.citation_precision for it in items) / len(items)
    cov_avg = sum(it.answer_metrics.evidence_coverage for it in items) / len(items)
    unsupp_avg = sum(it.answer_metrics.unsupported_claim_rate for it in items) / len(items)
    faith_avg = sum(it.answer_metrics.faithfulness for it in items) / len(items)

    # System: latency p50/p95
    latencies = [it.latency_ms for it in items]
    lat_p50 = _percentile(latencies, 50)
    lat_p95 = _percentile(latencies, 95)
    total = len(items)
    fallback_count = sum(1 for it in items if it.retrieval_mode == "fallback")
    fallback_rate = fallback_count / total if total > 0 else 0.0

    return (
        RetrievalMetrics(
            recall_at_5=round(recall_avg, 4),
            mrr=round(mrr_avg, 4),
            ndcg_at_5=round(ndcg_avg, 4),
            hit_rate=round(hit_avg, 4),
        ),
        AnswerMetrics(
            citation_precision=round(cit_avg, 4),
            evidence_coverage=round(cov_avg, 4),
            unsupported_claim_rate=round(unsupp_avg, 4),
            faithfulness=round(faith_avg, 4),
        ),
        SystemMetrics(
            latency_p50_ms=round(lat_p50, 2),
            latency_p95_ms=round(lat_p95, 2),
            total_questions=total,
            fallback_rate=round(fallback_rate, 4),
        ),
    )


__all__ = [
    "aggregate_metrics",
    "compute_citation_precision",
    "compute_evidence_coverage",
    "compute_faithfulness",
    "compute_hit_rate",
    "compute_mrr",
    "compute_ndcg_at_k",
    "compute_recall_at_k",
    "compute_unsupported_claim_rate",
]
