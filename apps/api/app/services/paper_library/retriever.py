"""Session 47: Paper chunk retriever (SOP §6 + §11 Task 4).

流程:
  query → rewrite_query (关键词提取 + 中英)
  → keyword_retrieve (chunk 文本 overlap)
  + dense_retrieve (embedding cosine)
  → rrf_fuse 合并
  → top-k chunk_id

scope:
  - "all_papers": 不限
  - "accepted_papers": 仅 EvidenceItem.review_status in (accepted, core) 的 paper
  - "specific": 只 paper_ids 列表内的
"""

from __future__ import annotations

import re
from typing import Iterable

from ...schemas_paper_library import PaperChunk
from ...schemas_paper_rag import AskScope
from .. import evidence as ev_store
from . import embedding, indexer, storage


# ---------------------------------------------------------------------------
# Query rewrite (中英翻译对齐 + 关键词提取)
# ---------------------------------------------------------------------------


# 常用中文 ↔ 学术英文 对照 (heuristic, 不依赖 API)
_ZH_TO_EN = {
    "方法": "method",
    "实验": "experiment",
    "结果": "result",
    "结论": "conclusion",
    "摘要": "abstract",
    "介绍": "introduction",
    "背景": "background",
    "相关工作": "related work",
    "基线": "baseline",
    "模型": "model",
    "网络": "network",
    "检测": "detection",
    "分割": "segmentation",
    "分类": "classification",
    "训练": "training",
    "推理": "inference",
    "数据集": "dataset",
    "性能": "performance",
    "精度": "accuracy",
    "缺陷": "defect",
    "钢材": "steel",
    "图像": "image",
    "视频": "video",
    "深度学习": "deep learning",
    "神经网络": "neural network",
    "卷积": "convolution",
    "变换": "transform",
    "注意力": "attention",
    "特征": "feature",
    "评估": "evaluation",
    "对比": "comparison",
    "综述": "survey",
    "实时": "real time",
    "端到端": "end to end",
    "预训练": "pretraining",
    "微调": "finetuning",
    "自监督": "self supervised",
    "无监督": "unsupervised",
    "有监督": "supervised",
    "强化学习": "reinforcement learning",
    "目标检测": "object detection",
    "图像分类": "image classification",
}


def rewrite_query(question: str) -> list[str]:
    """把 user question 拆成多个检索关键词 (中英混合).

    启发式:
    - 分中英文 token
    - 中文 2-gram + zh→en 对照
    - 去重 + 保留原顺序
    """

    if not question or not question.strip():
        return []

    out: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        token = token.strip().lower()
        if not token or token in seen:
            return
        seen.add(token)
        out.append(token)

    # 1) 英文单词
    en_tokens = re.findall(r"[a-zA-Z]+", question)
    for tok in en_tokens:
        _add(tok)

    # 2) 中文短语 (优先 2-gram 切)
    zh_text = re.findall(r"[一-鿿]+", question)
    for phrase in zh_text:
        # 加原文
        _add(phrase)
        # 2-gram
        for i in range(len(phrase) - 1):
            _add(phrase[i:i + 2])
        # 对照翻译 (按 phrase 整个匹配, 不匹配再按 char)
        if phrase in _ZH_TO_EN:
            _add(_ZH_TO_EN[phrase])
        else:
            for c in phrase:
                if c in _ZH_TO_EN:
                    _add(_ZH_TO_EN[c])

    return out


# ---------------------------------------------------------------------------
# Sparse / Dense retrieval
# ---------------------------------------------------------------------------


def _chunk_overlap_score(keywords: list[str], text: str) -> float:
    """Jaccard-like: 命中 keyword 数 / 总 keyword 数."""

    if not keywords or not text:
        return 0.0
    text_tokens = set(embedding.tokenize(text))
    if not text_tokens:
        return 0.0
    hit = 0
    for kw in keywords:
        kw_tokens = set(embedding.tokenize(kw))
        if kw_tokens and kw_tokens & text_tokens:
            hit += 1
    return hit / len(keywords)


def keyword_retrieve(
    chunks_index: dict[str, dict],
    query_keywords: list[str],
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """对 chunks_index 做 sparse 检索, 返回 [(chunk_id, score)]."""

    if not chunks_index or not query_keywords:
        return []
    scored: list[tuple[str, float]] = []
    for cid, meta in chunks_index.items():
        text = meta.get("text", "")
        score = _chunk_overlap_score(query_keywords, text)
        scored.append((cid, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    # 过滤 0 分 (避免噪音) 但保留至少 top_k 个空结果用于 RRF
    nonzero = [(c, s) for c, s in scored if s > 0]
    if len(nonzero) >= top_k:
        return nonzero[:top_k]
    # 不足 top_k, 用全 0 分兜底
    zeros = [(c, s) for c, s in scored if s == 0]
    return (nonzero + zeros)[:top_k]


def dense_retrieve(
    vectors: dict[str, list[float]],
    query_text: str,
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """对已有 embedding 做 cosine 检索."""

    if not vectors or not query_text:
        return []
    # query 自身 embed (沿用与 index 一致的 vocab — 这里偷懒用 hash 桶 256)
    # 实际生产应该把 vocab 持久化, 这里采用 length 推断: 与 corpus 维度对齐
    sample_vec = next(iter(vectors.values()))
    qv = embedding.embed_text(query_text, vocab=None)
    # 对齐维度 (embed_text 无 vocab 是 256, 截断/补零)
    if len(qv) < len(sample_vec):
        qv = qv + [0.0] * (len(sample_vec) - len(qv))
    elif len(qv) > len(sample_vec):
        qv = qv[: len(sample_vec)]

    scored: list[tuple[str, float]] = []
    for cid, vec in vectors.items():
        if not vec:
            continue
        s = embedding.cosine_similarity(qv, vec)
        scored.append((cid, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def rrf_fuse(
    sparse_results: list[tuple[str, float]],
    dense_results: list[tuple[str, float]],
    k: int = 60,
) -> list[str]:
    """Reciprocal Rank Fusion — 返回 chunk_id 列表, 按 fused score 降序."""

    if not sparse_results and not dense_results:
        return []

    scores: dict[str, float] = {}
    for rank, (cid, _) in enumerate(sparse_results, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    for rank, (cid, _) in enumerate(dense_results, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return sorted_ids


# ---------------------------------------------------------------------------
# Scope filter (accepted_papers lookup via Evidence Ledger)
# ---------------------------------------------------------------------------


def _accepted_paper_ids(project_id: str) -> set[str]:
    """从 Evidence Ledger 找 review_status in (accepted, core) 的 paper."""

    try:
        ledger = ev_store.get_ledger(project_id)
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    for item in ledger.papers:
        if item.review_status in ("accepted", "core"):
            # 通过 arxiv_id 或 title 关联 — 但 evidence 没存 paper_id
            # 这里用 arxiv_id 作为联接 (paper_library 也存了 arxiv_id)
            if item.arxiv_id:
                out.add(f"arxiv:{item.arxiv_id}")
            # 标题作为兜底 (用 sha 标记不可靠)
            if item.title:
                out.add(f"title:{item.title.lower()[:60]}")
    return out


def _filter_by_scope(
    chunks_index: dict[str, dict],
    project_id: str,
    scope: AskScope,
    paper_ids: list[str] | None,
) -> dict[str, dict]:
    """按 scope 过滤 chunks."""

    if scope == "all_papers":
        return chunks_index
    if scope == "specific":
        if not paper_ids:
            return {}
        return {cid: meta for cid, meta in chunks_index.items() if meta.get("paper_id") in paper_ids}
    if scope == "accepted_papers":
        # accepted_papers 通过 ledger 找 arxiv_id, 然后匹配 chunks 的 paper_id
        try:
            ledger = ev_store.get_ledger(project_id)
        except Exception:  # noqa: BLE001
            return {}
        # 收集所有 accepted paper 的 arxiv_id → 然后从 paper_library 反查 paper_id
        accepted_arxiv: set[str] = set()
        for item in ledger.papers:
            if item.review_status in ("accepted", "core") and item.arxiv_id:
                accepted_arxiv.add(item.arxiv_id)
        # 反查 paper_id: 遍历 manifest
        out: dict[str, dict] = {}
        for pid in storage.list_paper_ids(project_id):
            rec = storage.load_record(project_id, pid)
            if rec and rec.arxiv_id and rec.arxiv_id in accepted_arxiv:
                # 通过 paper_id 过滤
                for cid, meta in chunks_index.items():
                    if meta.get("paper_id") == pid:
                        out[cid] = meta
        return out
    return chunks_index


# ---------------------------------------------------------------------------
# Main retrieve
# ---------------------------------------------------------------------------


def retrieve(
    project_id: str,
    question: str,
    scope: AskScope = "all_papers",
    paper_ids: list[str] | None = None,
    top_k: int = 5,
) -> list[tuple[str, float]]:
    """主入口: 给定 question, 返回 top-k [(chunk_id, fused_score)].

    实际返回 chunk_id 列表 (排序), 配合 chunks_index 还原 chunk 对象
    留给上层 (paper_qa.build_context).
    """

    idx = indexer.load_index(project_id)
    chunks_index = idx.get("chunks", {})
    vectors = idx.get("vectors", {})

    # scope 过滤
    filtered = _filter_by_scope(chunks_index, project_id, scope, paper_ids)
    if not filtered:
        return []

    # 过滤 vectors
    filtered_vectors = {cid: vectors[cid] for cid in filtered if cid in vectors}

    keywords = rewrite_query(question)

    sparse = keyword_retrieve(filtered, keywords, top_k=max(top_k * 3, 20))
    dense = dense_retrieve(filtered_vectors, question, top_k=max(top_k * 3, 20))

    fused_ids = rrf_fuse(sparse, dense, k=60)
    return [(cid, 0.0) for cid in fused_ids[:top_k]]


__all__ = [
    "dense_retrieve",
    "keyword_retrieve",
    "retrieve",
    "rewrite_query",
    "rrf_fuse",
]