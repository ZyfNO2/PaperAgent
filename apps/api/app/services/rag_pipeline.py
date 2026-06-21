"""Session 34: RAG Pipeline — Sparse + Dense + RRF + Rerank.

面试级 RAG 实现：
1. SparseRetriever — 基于关键词匹配的 mock BM25
2. DenseRetriever — 基于 embedding 相似度的 mock dense (用标题+摘要的 token overlap 模拟)
3. RRF Fusion — Reciprocal Rank Fusion (Cormack et al. 2009)
4. Reranker — 多因子加权重排 (keyword match + URL verified + reproducibility + type coverage + recency)
5. CandidateResource 输出到 RagEvalReport

可接真实向量库，当前用 mock dense/sparse 实现可测合同。
"""

from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ..schemas_rag_eval import (
    DEFAULT_RAG_CONFIG,
    RagEvalReport,
    RagPipelineConfig,
    RagPipelineResponse,
    RetrievalCandidate,
)
from ..schemas_retrieval import QueryPlan, RetrievalCandidate as S14Candidate

# ---------------------------------------------------------------------------
# Locks / State
# ---------------------------------------------------------------------------

_LOCK = threading.RLock()
_RUNS: dict[str, list[dict]] = {}


def _runs(project_id: str) -> list[dict]:
    with _LOCK:
        return list(_RUNS.get(project_id, []))


def _add_run(project_id: str, record: dict) -> None:
    with _LOCK:
        _RUNS.setdefault(project_id, []).append(record)


def reset_rag_state() -> None:
    """测试用 — 清空所有 runs."""
    global _RUNS
    with _LOCK:
        _RUNS = {}


# ---------------------------------------------------------------------------
# Sparse Retriever (mock BM25)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """简单分词：英文按词切分，中文按字符切分."""
    if not text:
        return []
    # 英文单词
    text_lower = text.lower()
    tokens = re.findall(r"[a-z]+", text_lower)
    # 中文按字
    chinese_chars = re.findall(r"[一-鿿]", text)
    return tokens + chinese_chars


def _keyword_overlap_score(query_keywords: list[str], doc_text: str) -> float:
    """计算 query keywords 与 doc text 的归一化 overlap.

    使用 Jaccard 系数。
    """
    if not query_keywords or not doc_text:
        return 0.0
    doc_tokens = set(_tokenize(doc_text))
    if not doc_tokens:
        return 0.0
    matched = 0
    for kw in query_keywords:
        kw_tokens = set(_tokenize(kw))
        if kw_tokens and kw_tokens & doc_tokens:
            matched += 1
    return matched / len(query_keywords) if query_keywords else 0.0


def sparse_retrieve(
    candidates: list[S14Candidate],
    query_keywords: list[str],
    top_k: int = 20,
) -> list[tuple[S14Candidate, float]]:
    """Mock BM25 sparse retrieval — 基于关键词 overlap.

    返回按分数排序的 (candidate, score) 列表。
    """
    if not candidates:
        return []
    scored = []
    for cand in candidates:
        # 综合 title + abstract + venue
        text = " ".join(filter(None, [cand.title, cand.abstract or "", cand.venue or ""]))
        score = _keyword_overlap_score(query_keywords, text)
        scored.append((cand, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Dense Retriever (mock)
# ---------------------------------------------------------------------------


def _semantic_proxy_score(query_keywords: list[str], cand: S14Candidate) -> float:
    """Mock dense embedding 相似度.

    真实场景会调 embedding API。当前用「title token overlap + year weight」做 proxy，
    保证 deterministic & testable。
    """
    if not query_keywords:
        return 0.0
    text = " ".join(filter(None, [cand.title, cand.abstract or ""]))
    doc_tokens = set(_tokenize(text))
    if not doc_tokens:
        return 0.0
    matched = 0
    for kw in query_keywords:
        kw_tokens = set(_tokenize(kw))
        if kw_tokens and kw_tokens & doc_tokens:
            matched += len(kw_tokens & doc_tokens)
    semantic = matched / (len(doc_tokens) + 1)  # 归一化
    # year weight: 越新越接近 1
    year_weight = 0.5
    if cand.year:
        current_year = datetime.now(timezone.utc).year
        delta = max(0, current_year - cand.year)
        year_weight = max(0.5, 1.0 - delta * 0.05)
    return min(1.0, semantic * 1.5) * year_weight


def dense_retrieve(
    candidates: list[S14Candidate],
    query_keywords: list[str],
    top_k: int = 20,
) -> list[tuple[S14Candidate, float]]:
    """Mock dense retrieval — 基于语义 proxy."""
    if not candidates:
        return []
    scored = []
    for cand in candidates:
        score = _semantic_proxy_score(query_keywords, cand)
        scored.append((cand, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# RRF Fusion (Reciprocal Rank Fusion)
# ---------------------------------------------------------------------------


def rrf_fuse(
    sparse_results: list[tuple[S14Candidate, float]],
    dense_results: list[tuple[S14Candidate, float]],
    k: int = 60,
) -> list[S14Candidate]:
    """Reciprocal Rank Fusion — Cormack et al. 2009.

    score = sum(1 / (k + rank)) over each retriever.
    返回按 fused_score 排序的 candidates.
    """
    if not sparse_results and not dense_results:
        return []

    # 累计 RRF 分数
    rrf_scores: dict[str, float] = {}
    cand_by_id: dict[str, S14Candidate] = {}

    for rank, (cand, _sparse_score) in enumerate(sparse_results, start=1):
        cid = cand.candidate_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
        cand_by_id[cid] = cand

    for rank, (cand, _dense_score) in enumerate(dense_results, start=1):
        cid = cand.candidate_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
        cand_by_id[cid] = cand

    # 按 rrf score 排序
    sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    return [cand_by_id[cid] for cid in sorted_cids]


# ---------------------------------------------------------------------------
# Reranker — 多因子加权
# ---------------------------------------------------------------------------


def _compute_keyword_match(query_keywords: list[str], cand: RetrievalCandidate) -> tuple[float, list[str]]:
    """0..1, 关键词匹配分数, 同时返回 matched list."""
    text = " ".join(filter(None, [cand.title, cand.abstract or ""]))
    matched: list[str] = []
    for kw in query_keywords:
        kw_tokens = set(_tokenize(kw))
        text_tokens = set(_tokenize(text))
        if kw_tokens and kw_tokens & text_tokens:
            matched.append(kw)
    score = len(matched) / max(1, len(query_keywords))
    return score, matched


def _compute_reproducibility(cand: RetrievalCandidate) -> float:
    """代码/数据集的可复现信号.

    paper: 有代码链接 + 数据集 = 高
    repo: 有 license + readme = 高
    dataset: 有 license + download = 高
    """
    if cand.kind == "paper":
        if cand.repo_full_name or cand.dataset_slug:
            return 1.0
        return 0.5
    if cand.kind == "repo":
        if cand.license and cand.stars and cand.stars > 10:
            return 1.0
        return 0.6
    if cand.kind == "dataset":
        if cand.license and cand.url:
            return 1.0
        return 0.7
    return 0.5


def _compute_recency(cand: RetrievalCandidate) -> float:
    """越近的论文分数越高."""
    if not cand.year:
        return 0.5
    current_year = datetime.now(timezone.utc).year
    delta = max(0, current_year - cand.year)
    return max(0.3, 1.0 - delta * 0.05)


def rerank_candidates(
    candidates: list[RetrievalCandidate],
    query_keywords: list[str],
    config: RagPipelineConfig,
) -> list[RetrievalCandidate]:
    """多因子加权 rerank.

    因子：
    1. keyword match — 关键词重叠率
    2. url verified — URL 可用性
    3. reproducibility — 复现信号
    4. type coverage — 多类型覆盖
    5. recency — 时效性
    """
    if not candidates:
        return []

    # 类型分布：用于 type coverage 加权
    type_counts: dict[str, int] = {}
    for c in candidates:
        type_counts[c.kind] = type_counts.get(c.kind, 0) + 1
    type_total = sum(type_counts.values()) or 1
    type_share = {k: v / type_total for k, v in type_counts.items()}

    reranked: list[RetrievalCandidate] = []
    for cand in candidates:
        kw_score, matched = _compute_keyword_match(query_keywords, cand)
        cand.matched_keywords = matched

        url_score = 1.0 if cand.url_verified else 0.4

        repro_score = _compute_reproducibility(cand)

        # type coverage: 少数类型加权
        type_score = 1.0 - type_share.get(cand.kind, 0.0)

        recency_score = _compute_recency(cand)

        rerank_score = (
            config.w_keyword_match * kw_score
            + config.w_url_verified * url_score
            + config.w_reproducibility * repro_score
            + config.w_type_coverage * type_score
            + config.w_recency * recency_score
        )
        cand.rerank_score = round(min(1.0, max(0.0, rerank_score)), 4)

        # 记录 rerank reason（用于 UI 解释排序）
        reasons = []
        if kw_score > 0.7:
            reasons.append(f"关键词高匹配 ({kw_score:.2f})")
        elif kw_score < config.min_keyword_overlap:
            reasons.append(f"关键词低匹配 ({kw_score:.2f})")
        if cand.url_verified:
            reasons.append("URL 已验证")
        else:
            reasons.append("URL 未验证 (-0.6)")
        if cand.kind == "repo" and cand.stars and cand.stars > 100:
            reasons.append(f"高星标 ({cand.stars})")
        if cand.kind == "paper" and cand.citation_count and cand.citation_count > 100:
            reasons.append(f"高引用 ({cand.citation_count})")
        cand.rerank_reasons = reasons

        # URL 未验证大幅降权
        if not cand.url_verified:
            cand.rerank_score = round(cand.rerank_score * 0.4, 4)

        reranked.append(cand)

    reranked.sort(key=lambda c: c.rerank_score, reverse=True)
    return reranked


# ---------------------------------------------------------------------------
# Convert S14 candidate → S34 RetrievalCandidate
# ---------------------------------------------------------------------------


def _convert_candidate(s14: S14Candidate, query_id: str = "") -> RetrievalCandidate:
    """从 S14 candidate 转成 S34 RAG candidate."""
    return RetrievalCandidate(
        candidate_id=s14.candidate_id,
        project_id=s14.project_id,
        kind=s14.candidate_type if s14.candidate_type in ("paper", "dataset", "repo") else "paper",
        title=s14.title,
        url=s14.url,
        source=s14.source,
        query_id=query_id,
        year=s14.year,
        authors=list(s14.authors or []),
        abstract=s14.abstract,
        venue=s14.venue,
        doi=s14.doi,
        arxiv_id=s14.arxiv_id,
        openalex_id=s14.openalex_id,
        semantic_scholar_id=s14.semantic_scholar_id,
        repo_full_name=s14.repo_full_name,
        dataset_slug=s14.dataset_slug,
        license=s14.license,
        stars=s14.stars,
        citation_count=s14.citation_count,
        updated_at=s14.updated_at,
        url_verified=False,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_rag_pipeline(
    project_id: str,
    s14_candidates: list[S14Candidate],
    query_keywords: list[str],
    config: RagPipelineConfig | None = None,
) -> dict:
    """执行完整 RAG pipeline.

    流程：sparse → dense → RRF fusion → rerank → top-k final
    """
    cfg = config or DEFAULT_RAG_CONFIG

    if not s14_candidates:
        return {
            "run_id": f"rag_{uuid.uuid4().hex[:10]}",
            "candidates": [],
            "sparse_results": [],
            "dense_results": [],
            "config": cfg,
            "status": "completed",
            "message": "no candidates to process",
        }

    # 1) Sparse retrieval
    sparse_results = sparse_retrieve(s14_candidates, query_keywords, top_k=cfg.top_k_sparse)
    # 2) Dense retrieval
    dense_results = dense_retrieve(s14_candidates, query_keywords, top_k=cfg.top_k_dense)

    # 3) RRF fusion
    fused = rrf_fuse(sparse_results, dense_results, k=cfg.rrf_k)

    # 4) 转换为 S34 candidates + 写 fused_score
    fused_candidates: list[RetrievalCandidate] = []
    sparse_by_id = {c.candidate_id: s for c, s in sparse_results}
    dense_by_id = {c.candidate_id: s for c, s in dense_results}
    max_fused = len(fused)
    for rank, s14 in enumerate(fused, start=1):
        rag_cand = _convert_candidate(s14, query_id=f"q_{rank}")
        rag_cand.sparse_score = round(sparse_by_id.get(s14.candidate_id, 0.0), 4)
        rag_cand.dense_score = round(dense_by_id.get(s14.candidate_id, 0.0), 4)
        # Fused score 用归一化的 RRF: max-rank = max_fused
        rag_cand.fused_score = round(1.0 - (rank - 1) / max(1, max_fused), 4)
        fused_candidates.append(rag_cand)

    # 截断到 top_k_fused
    fused_candidates = fused_candidates[: cfg.top_k_fused]

    # 5) Rerank
    reranked = rerank_candidates(fused_candidates, query_keywords, cfg)

    # 6) 截断到 top_k_final + 过滤低分
    final = [c for c in reranked if c.rerank_score >= cfg.min_rerank_score][: cfg.top_k_final]

    run_id = f"rag_{uuid.uuid4().hex[:10]}"

    # 写入 run 记录
    record = {
        "run_id": run_id,
        "project_id": project_id,
        "sparse_count": len(sparse_results),
        "dense_count": len(dense_results),
        "fused_count": len(fused_candidates),
        "final_count": len(final),
        "config": cfg.model_dump(),
        "created_at": _now_iso(),
    }
    _add_run(project_id, record)

    return {
        "run_id": run_id,
        "candidates": final,
        "sparse_results": [(c.candidate_id, s) for c, s in sparse_results],
        "dense_results": [(c.candidate_id, s) for c, s in dense_results],
        "fused_count": len(fused_candidates),
        "config": cfg,
        "status": "completed" if final else "partial",
        "message": "" if final else "no candidates passed rerank threshold",
    }


def get_last_run(project_id: str) -> Optional[dict]:
    runs = _runs(project_id)
    return runs[-1] if runs else None


def list_runs(project_id: str) -> list[dict]:
    return _runs(project_id)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()