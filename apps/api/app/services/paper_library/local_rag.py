"""Session 60 M2 + M3: LocalRagIndexService + LocalRagAskService.

M2 — LocalRagIndexService (build_index_status):
  复用 indexer.build_index / load_index.
  汇总 project 的索引状态 (总 paper / chunk / indexed chunk).

M3 — LocalRagAskService (ask_local_rag):
  复用 retriever.retrieve (scope="all_papers").
  生成 extractive answer + evidence refs.
  没有命中时返回明确的 no-hit 信号, 不编造答案.

不依赖:
- LLM (全部 extractive / heuristic)
- Evidence Ledger (scope 强制 all_papers, 不接 accepted_papers 过滤)
- 外部 embedding API (沿用现有 mock embedding)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import embedding, indexer, storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# M2: Index status
# ---------------------------------------------------------------------------


@dataclass
class PaperIndexEntry:
    paper_id: str
    title: str
    chunk_count: int
    indexed_chunk_count: int

    @property
    def is_indexed(self) -> bool:
        return self.chunk_count > 0 and self.indexed_chunk_count >= self.chunk_count


@dataclass
class IndexStatus:
    project_id: str
    total_papers: int
    total_chunks: int
    indexed_chunks: int
    unindexed_chunks: int
    embedding_provider: str
    papers: list[PaperIndexEntry] = field(default_factory=list)


def build_index_for_project(
    project_id: str,
    paper_ids: list[str] | None = None,
    force: bool = False,
) -> dict:
    """建索引 (整个 project 或指定 paper_ids).

    透传 indexer.build_index, 返回统一 dict.
    """

    return indexer.build_index(project_id, paper_ids=paper_ids, force=force)


def get_index_status(project_id: str) -> IndexStatus:
    """汇总 project 当前索引状态.

    步骤:
    1) list_paper_ids → paper_ids 列表
    2) load_index → 已索引 chunks_index
    3) 逐 paper 统计: chunk_count vs indexed_chunk_count
    """

    paper_ids = storage.list_paper_ids(project_id)
    idx = indexer.load_index(project_id)
    indexed_chunk_ids = set(idx.get("chunks", {}).keys())

    papers: list[PaperIndexEntry] = []
    total_chunks = 0
    indexed_total = 0
    for pid in paper_ids:
        rec = storage.load_record(project_id, pid)
        title = rec.title if rec else "(unknown)"
        chunks = storage.load_chunks(project_id, pid)
        cc = len(chunks)
        ic = sum(1 for c in chunks if c.chunk_id in indexed_chunk_ids)
        papers.append(PaperIndexEntry(
            paper_id=pid, title=title,
            chunk_count=cc, indexed_chunk_count=ic,
        ))
        total_chunks += cc
        indexed_total += ic

    return IndexStatus(
        project_id=project_id,
        total_papers=len(paper_ids),
        total_chunks=total_chunks,
        indexed_chunks=indexed_total,
        unindexed_chunks=total_chunks - indexed_total,
        embedding_provider=embedding.get_embedding_provider(),
        papers=papers,
    )


# ---------------------------------------------------------------------------
# M3: Local ask (纯本地检索 + extractive answer)
# ---------------------------------------------------------------------------


@dataclass
class LocalEvidenceRef:
    paper_id: str
    chunk_id: str
    section_title: str | None
    chunk_type: str | None
    page_start: int | None
    page_end: int | None
    quote: str
    score: float


@dataclass
class LocalAskOutcome:
    question: str
    answer: str
    evidence_refs: list[LocalEvidenceRef] = field(default_factory=list)
    retrieval_mode: str = "local_embedding"  # "local_embedding" / "no_hit"
    confidence: float = 0.0
    no_hit: bool = False
    message: str = ""


def _truncate(text: str, n: int = 200) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n].rstrip()


def _build_extractive_answer(question: str, chunks: list[dict]) -> str:
    """没有 LLM 时, 拼接 top chunks 形成 extractive answer.

    严格只摘抄, 不生成新断言.
    """

    if not chunks:
        return ""
    snippets: list[str] = []
    for i, c in enumerate(chunks[:5], start=1):
        section = c.get("section_title") or "Body"
        text = (c.get("text", "") or "").strip()
        if not text:
            continue
        snippets.append(f"[{i}] {section}: {text[:400]}")
    if not snippets:
        return ""
    return (
        f"根据本地文献库检索, 与问题相关的片段摘录如下:\n\n"
        + "\n\n".join(snippets)
    )


def _compute_confidence(refs: list[LocalEvidenceRef], total_chunks: int) -> float:
    """heuristic confidence: 有命中就有 base, 引用越多 confidence 越高.

    上限 1.0. 简单公式: min(1.0, sum(score) / total_chunks + 0.2 * len(refs)).
    """

    if not refs or total_chunks <= 0:
        return 0.0
    avg_score = sum(max(0.0, min(1.0, r.score)) for r in refs) / len(refs)
    return min(1.0, avg_score * 0.6 + 0.2 * len(refs))


def ask_local_rag(
    project_id: str,
    question: str,
    top_k: int = 3,
    paper_ids: list[str] | None = None,
) -> LocalAskOutcome:
    """本地问答主入口.

    不依赖 LLM, 不依赖 Evidence Ledger.
    返回 extractive answer + evidence refs.
    """

    if not question or not question.strip():
        return LocalAskOutcome(
            question=question or "",
            answer="问题不能为空.",
            retrieval_mode="no_hit",
            confidence=0.0,
            no_hit=True,
            message="question 为空",
        )

    # 1) 索引状态
    idx = indexer.load_index(project_id)
    chunks_index = idx.get("chunks", {})
    vectors = idx.get("vectors", {})

    if not chunks_index:
        return LocalAskOutcome(
            question=question,
            answer="未在本地文献库中找到证据，无法回答该问题。",
            retrieval_mode="no_hit",
            confidence=0.0,
            no_hit=True,
            message="本地索引为空, 请先添加文献并执行索引",
        )

    # 2) 过滤 paper_ids (若有指定)
    target_paper_ids = set(paper_ids) if paper_ids else None
    filtered_chunks_index: dict[str, dict] = {}
    for cid, meta in chunks_index.items():
        pid = meta.get("paper_id", "")
        if target_paper_ids is None or pid in target_paper_ids:
            filtered_chunks_index[cid] = meta

    if not filtered_chunks_index:
        return LocalAskOutcome(
            question=question,
            answer="未在本地文献库中找到证据，无法回答该问题。",
            retrieval_mode="no_hit",
            confidence=0.0,
            no_hit=True,
            message="指定 paper_ids 无索引",
        )

    # 3) 调用既有 keyword_retrieve (轻量 utility) + 本地 vocab-aware dense
    #    不调 retriever.retrieve —— 它依赖 Evidence Ledger scope 过滤 (M3 禁止),
    #    且 dense_retrieve 用 vocab=None 与实际 index 维度不一致, 会产生伪命中.
    from . import retriever as _retriever
    keywords = _retriever.rewrite_query(question)
    sparse = _retriever.keyword_retrieve(filtered_chunks_index, keywords, top_k=max(top_k * 3, 20))

    # 用 chunks_index + vectors 直接做 vocab-aware dense (复用 indexer.embed_corpus 的 vocab)
    vocab = embedding.get_vocab()
    sample_vec = next(iter(vectors.values()), None) if vectors else None
    dense: list[tuple[str, float]] = []
    if sample_vec is not None:
        qv = embedding.embed_text(question, vocab=vocab) if vocab else embedding.embed_text(question, vocab=None)
        if len(qv) < len(sample_vec):
            qv = qv + [0.0] * (len(sample_vec) - len(qv))
        elif len(qv) > len(sample_vec):
            qv = qv[: len(sample_vec)]
        for cid, vec in vectors.items():
            if cid not in filtered_chunks_index:
                continue
            if not vec:
                continue
            dense.append((cid, embedding.cosine_similarity(qv, vec)))
        dense.sort(key=lambda x: x[1], reverse=True)
        dense = dense[: max(top_k * 3, 20)]

    fused_ids = _retriever.rrf_fuse(sparse, dense, k=60)
    hits: list[tuple[str, float]] = [(cid, 0.0) for cid in fused_ids[:top_k]]

    if not hits:
        return LocalAskOutcome(
            question=question,
            answer="未在本地文献库中找到证据，无法回答该问题。",
            retrieval_mode="no_hit",
            confidence=0.0,
            no_hit=True,
            message="retriever 未返回命中",
        )

    # 4) 取 top chunks 元数据 (过滤 score=0 的"假命中")
    top_chunk_metas: list[dict] = []
    refs: list[LocalEvidenceRef] = []
    for rank, (cid, score) in enumerate(hits[:top_k]):
        meta = chunks_index.get(cid)
        if not meta:
            continue
        meta = dict(meta)
        meta["chunk_id"] = cid
        meta["rank"] = rank
        # 用 vocab-aware cosine (与 index 一致) — vocab=None 会产出 hash-bucket 256 维,
        # 与 chunk 的 vocab-based 维度不一致, 截断后是随机噪声, score ≈ 0 → 误判 no_hit.
        if cid in vectors:
            qv2 = embedding.embed_text(question, vocab=vocab) if vocab else embedding.embed_text(question, vocab=None)
            sv = vectors[cid]
            if qv2 and sv:
                if len(qv2) < len(sv):
                    qv2 = qv2 + [0.0] * (len(sv) - len(qv2))
                elif len(qv2) > len(sv):
                    qv2 = qv2[: len(sv)]
                meta["score"] = embedding.cosine_similarity(qv2, sv)
            else:
                meta["score"] = 0.0
        else:
            meta["score"] = 0.0
        # ponytail: retriever 的 RRF 在 sparse 全 0 / dense 弱匹配时仍会返回 top-k
        # fused_id 列表, 但实际无相关 chunk. 过滤 score==0 避免假命中.
        if meta["score"] <= 0.0:
            continue
        top_chunk_metas.append(meta)
        refs.append(LocalEvidenceRef(
            paper_id=meta.get("paper_id", ""),
            chunk_id=cid,
            section_title=meta.get("section_title"),
            chunk_type=meta.get("chunk_type"),
            page_start=meta.get("page_start"),
            page_end=meta.get("page_end"),
            quote=_truncate(meta.get("text", "") or "", 200),
            score=float(meta.get("score", 0.0)),
        ))

    if not refs:
        return LocalAskOutcome(
            question=question,
            answer="未在本地文献库中找到证据，无法回答该问题。",
            retrieval_mode="no_hit",
            confidence=0.0,
            no_hit=True,
            message="所有候选 chunk 相似度为 0, 视为未命中",
        )

    answer = _build_extractive_answer(question, top_chunk_metas) or "未在本地文献库中找到证据，无法回答该问题。"
    confidence = _compute_confidence(refs, total_chunks=len(chunks_index))

    return LocalAskOutcome(
        question=question,
        answer=answer,
        evidence_refs=refs,
        retrieval_mode="local_embedding",
        confidence=round(confidence, 4),
        no_hit=False,
        message=f"命中 {len(refs)} chunks",
    )


__all__ = [
    "IndexStatus",
    "LocalAskOutcome",
    "LocalEvidenceRef",
    "PaperIndexEntry",
    "ask_local_rag",
    "build_index_for_project",
    "get_index_status",
]