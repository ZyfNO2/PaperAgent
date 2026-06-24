"""Paper Library API (Session 46 + Session 47).

Session 46 4 端点:
- POST /api/v1/projects/{project_id}/paper-library/arxiv
- POST /api/v1/projects/{project_id}/paper-library/upload
- GET  /api/v1/projects/{project_id}/paper-library
- GET  /api/v1/projects/{project_id}/paper-library/{paper_id}

Session 47 新增 2 端点 (Paper RAG):
- POST /api/v1/projects/{project_id}/paper-library/{paper_id}/index
- POST /api/v1/projects/{project_id}/paper-library/ask
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ...schemas_paper_library import (
    ArxivIngestRequest,
    ArxivIngestResponse,
    LocalUploadIngestRequest,
    LocalUploadIngestResponse,
    PaperDetailChunkPreview,
    PaperDetailResponse,
    PaperListResponse,
)
from ...schemas_paper_rag import (
    PaperIndexRequest,
    PaperIndexResponse,
    PaperRAGAnswer,
    PaperRAGAskRequest,
)
from ...services import paper_library as pl_service
from ...services.paper_library import indexer, paper_qa, reranker, retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["paper-library"])


# ---------- arXiv ingest ---------- #


@router.post(
    "/{project_id}/paper-library/arxiv",
    response_model=ArxivIngestResponse,
)
def ingest_arxiv_paper(project_id: str, body: ArxivIngestRequest) -> ArxivIngestResponse:
    try:
        outcome = pl_service.ingest_arxiv(project_id, body.arxiv_id_or_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingest_arxiv failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"arXiv ingest failed: {exc}")

    return ArxivIngestResponse(
        paper_id=outcome.paper_id,
        status="duplicate" if outcome.is_duplicate else (
            "ingested" if outcome.parse_status in ("parsed", "skipped") else "failed"
        ),
        parse_status=outcome.parse_status,  # type: ignore[arg-type]
        chunk_count=outcome.chunk_count,
        evidence_id=outcome.evidence_id,
        is_duplicate=outcome.is_duplicate,
        message=outcome.message,
    )


# ---------- 本地 upload ---------- #


@router.post(
    "/{project_id}/paper-library/upload",
    response_model=LocalUploadIngestResponse,
)
def ingest_local_upload(project_id: str, body: LocalUploadIngestRequest) -> LocalUploadIngestResponse:
    try:
        outcome = pl_service.ingest_upload(
            project_id, body.filename, body.content_b64, body.mime,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingest_upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"upload ingest failed: {exc}")

    return LocalUploadIngestResponse(
        paper_id=outcome.paper_id,
        parse_status=outcome.parse_status,  # type: ignore[arg-type]
        chunk_count=outcome.chunk_count,
        evidence_id=outcome.evidence_id,
        is_duplicate=outcome.is_duplicate,
        message=outcome.message,
    )


# ---------- 列表 ---------- #


@router.get(
    "/{project_id}/paper-library",
    response_model=PaperListResponse,
)
def list_papers(project_id: str) -> PaperListResponse:
    papers = pl_service.list_papers(project_id)
    total_chunks = sum(p.chunk_count for p in papers)
    return PaperListResponse(
        project_id=project_id,
        papers=papers,
        total_chunks=total_chunks,
        total_papers=len(papers),
    )


# ---------- 详情 ---------- #


@router.get(
    "/{project_id}/paper-library/{paper_id}",
    response_model=PaperDetailResponse,
)
def get_paper_detail(project_id: str, paper_id: str) -> PaperDetailResponse:
    rec = pl_service.get_paper(project_id, paper_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"paper_id {paper_id} 不存在")
    chunks = pl_service.get_paper_chunks(project_id, paper_id)
    excerpt = pl_service.get_paper_text_excerpt(project_id, paper_id)

    previews: list[PaperDetailChunkPreview] = []
    for c in chunks[:3]:
        previews.append(PaperDetailChunkPreview(
            chunk_id=c.chunk_id,
            section_title=c.section_title,
            section_path=c.section_path,
            chunk_type=c.chunk_type,
            token_count=c.token_count,
            text_preview=(c.text or "")[:200],
        ))

    return PaperDetailResponse(
        paper=rec,
        chunks=previews,
        full_text_excerpt=excerpt[:1500] if excerpt else "",
        chunk_total=len(chunks),
    )


# ===========================================================================
# Session 47: Paper RAG — Index + Ask
# ===========================================================================


@router.post(
    "/{project_id}/paper-library/{paper_id}/index",
    response_model=PaperIndexResponse,
)
def index_paper(project_id: str, paper_id: str, body: PaperIndexRequest | None = None) -> PaperIndexResponse:
    """为指定 paper (或整个 project) 建 embedding 索引.

    body.force=true 时强制重建 (忽略已索引).
    """

    force = bool(body.force) if body else False
    try:
        result = indexer.build_index(project_id, paper_ids=[paper_id], force=force)
    except Exception as exc:  # noqa: BLE001
        logger.warning("build_index failed for %s: %s", paper_id, exc)
        raise HTTPException(status_code=500, detail=f"index failed: {exc}")
    return PaperIndexResponse(
        paper_id=paper_id,
        chunk_count=int(result.get("chunk_count", 0)),
        indexed=int(result.get("indexed", 0)),
        skipped=int(result.get("skipped", 0)),
        duration_ms=int(result.get("duration_ms", 0)),
    )


@router.post(
    "/{project_id}/paper-library/ask",
    response_model=PaperRAGAnswer,
)
def ask_paper_library(project_id: str, body: PaperRAGAskRequest) -> PaperRAGAnswer:
    """Paper RAG 问答: query rewrite → retrieve → rerank → LLM → answer.

    LLM 失败: 自动 fallback (retrieval_mode=fallback, confidence=0).
    无命中: 明说"未在论文库中找到证据".
    """

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    # 1) 检索
    try:
        hits = retriever.retrieve(
            project_id=project_id,
            question=question,
            scope=body.scope,
            paper_ids=body.paper_ids,
            top_k=body.top_k,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("retrieve failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"retrieve failed: {exc}")

    idx = indexer.load_index(project_id)
    chunks_index = idx.get("chunks", {})

    # 2) 还原 chunk 元数据 + 计算 paper year lookup
    raw_chunks: list[dict] = []
    paper_year_lookup: dict[str, int | None] = {}
    for cid, _score in hits:
        meta = chunks_index.get(cid)
        if not meta:
            continue
        meta = dict(meta)
        meta["chunk_id"] = cid
        raw_chunks.append(meta)
        pid = meta.get("paper_id")
        if pid and pid not in paper_year_lookup:
            rec = pl_service.get_paper(project_id, pid)
            paper_year_lookup[pid] = rec.year if rec else None

    # 3) reranker
    reranked = reranker.rerank_chunks(
        question,
        [(meta, 0.0) for meta in raw_chunks],
        paper_year_lookup=paper_year_lookup,
    )
    top_chunks = [meta for meta, _ in reranked[: body.top_k]]

    if not top_chunks:
        # 无命中: 返回 no-hit answer
        from ...schemas_paper_rag import PaperRAGAnswer as _Answer
        return _Answer(
            question=question,
            answer="未在论文库中找到证据，无法回答该问题。",
            evidence_refs=[],
            unsupported_claims=[],
            confidence=0.0,
            used_papers=[],
            retrieval_mode="llm",  # type: ignore[arg-type]
        )

    # 4) 加载 paper titles 供 context
    used_paper_ids = sorted({c.get("paper_id", "") for c in top_chunks if c.get("paper_id")})
    paper_titles = paper_qa.load_paper_titles(project_id, used_paper_ids)

    # 5) LLM 问答 (失败 → fallback)
    try:
        answer = paper_qa.answer_with_llm(question, top_chunks, paper_titles=paper_titles)
    except Exception as exc:  # noqa: BLE001
        logger.info("paper_qa LLM fallback (reason=%s)", exc)
        answer = paper_qa.fallback_answer(question, top_chunks)

    return answer
