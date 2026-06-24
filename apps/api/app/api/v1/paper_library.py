"""Paper Library API (Session 46).

4 个端点:
- POST /api/v1/projects/{project_id}/paper-library/arxiv
- POST /api/v1/projects/{project_id}/paper-library/upload
- GET  /api/v1/projects/{project_id}/paper-library
- GET  /api/v1/projects/{project_id}/paper-library/{paper_id}
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
from ...services import paper_library as pl_service

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
