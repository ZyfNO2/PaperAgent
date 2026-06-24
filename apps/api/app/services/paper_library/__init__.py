"""Paper Library service (Session 46).

主入口:
- ingest_arxiv(project_id, arxiv_id_or_url) → IngestOutcome
- ingest_upload(project_id, filename, content_b64, mime?) → IngestOutcome
- list_papers(project_id) → list[PaperRecord]
- get_paper(project_id, paper_id) → PaperRecord | None
- get_paper_chunks(project_id, paper_id) → list[PaperChunk]
- get_paper_text_excerpt(project_id, paper_id) → str

入库成功后会调 evidence.add_paper_manual 生成 EvidenceItem(pending).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from ...schemas_evidence import PaperManualCreate
from ...schemas_paper_library import (
    LocalUploadIngestRequest,
    LocalUploadIngestResponse,
    PaperChunk,
    PaperRecord,
)
from .. import evidence as ev_store
from . import arxiv_downloader, chunker, dedup, local_upload, metadata_resolver, pdf_parser, storage

logger = logging.getLogger(__name__)


# ---------- 结果 ---------- #


@dataclass
class IngestOutcome:
    paper_id: str
    parse_status: str
    chunk_count: int
    is_duplicate: bool
    evidence_id: str | None
    record: PaperRecord
    message: str = ""


# ---------- 公共: 创建 paper_id ---------- #


def _make_paper_id(source_mode: str) -> str:
    prefix = "ax" if source_mode == "arxiv_download" else "up"
    return f"paper_{prefix}_{uuid.uuid4().hex[:10]}"


# ---------- 公共: 落盘 + Evidence 联动 ---------- #


def _persist(record: PaperRecord, chunks: list[PaperChunk], sha: str | None) -> tuple[str, str]:
    record_path = storage.save_paper_record(record)
    chunks_path = storage.save_chunks(chunks) if chunks else ""
    storage.update_manifest(
        project_id=record.project_id,
        paper_id=record.paper_id,
        record_path=record_path,
        chunks_path=chunks_path,
        chunk_count=len(chunks),
        parse_status=record.parse_status,
        source_mode=record.source_mode,
        sha256=sha,
        arxiv_id=record.arxiv_id,
    )
    return record_path, chunks_path


def _link_evidence(record: PaperRecord) -> str | None:
    """入 Evidence Ledger: 生成 EvidenceItem(pending).

    arXiv → source_mode=auto_search (SOP §5: 自动检索源)
    upload → source_mode=upload (SOP §5: 上传源)
    """

    try:
        body = PaperManualCreate(
            title=record.title,
            authors=record.authors,
            year=record.year,
            url=record.url,
            doi=record.doi,
            arxiv_id=record.arxiv_id,
            abstract=None,
            user_note=f"Ingested from {record.source_mode} (parse={record.parse_status})",
            tags=["paper_library", record.source_mode],
            review_status="pending",
        )
        resp = ev_store.add_paper_manual(record.project_id, body)
        return resp.evidence_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("evidence link failed for %s: %s", record.paper_id, exc)
        return None


# ---------- arXiv ingest ---------- #


def ingest_arxiv(project_id: str, arxiv_id_or_url: str) -> IngestOutcome:
    """arXiv ID/URL → PDF 下载 → 解析 → 切块 → 落盘 → Evidence."""

    fetch = arxiv_downloader.fetch_arxiv(arxiv_id_or_url)
    arxiv_id = fetch.arxiv_id

    # sha256
    sha = None
    pdf_bytes = fetch.pdf_bytes
    if pdf_bytes:
        sha = local_upload.compute_sha256(pdf_bytes)

    # 解析全文
    full_text = ""
    page_count = 0
    parse_status = fetch.parse_status
    if pdf_bytes and len(pdf_bytes) > 100:
        parsed = pdf_parser.parse(pdf_bytes)
        full_text = parsed.get("text", "") or ""
        page_count = parsed.get("page_count", 0) or 0
        # pdf_parser 给的 status 优先
        ps = parsed.get("status", "failed")
        if ps == "parsed" and full_text:
            parse_status = "parsed"
        elif ps == "skipped" and not full_text:
            parse_status = "skipped"
        else:
            parse_status = "failed"

    # metadata
    meta = metadata_resolver.resolve_combined(
        arxiv_id=arxiv_id,
        arxiv_title=fetch.title,
        arxiv_authors=fetch.authors,
        arxiv_year=fetch.year,
        arxiv_summary=fetch.summary,
        arxiv_url=fetch.abs_url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None),
        pdf_text=full_text,
    )
    metadata_status = "resolved" if (meta.get("title") and not meta["title"].startswith("arXiv:")) else (
        "partial" if meta.get("title") else "missing"
    )

    # 重复检测
    existing_records = _load_existing_records(project_id)
    dup = dedup.find_duplicate(
        new_sha256=sha,
        new_doi=meta.get("doi"),
        new_arxiv_id=meta.get("arxiv_id") or arxiv_id,
        new_title=meta.get("title") or f"arXiv:{arxiv_id}",
        new_year=meta.get("year"),
        existing=existing_records,
    )
    if dup:
        return IngestOutcome(
            paper_id=dup.paper_id,
            parse_status=dup.parse_status,
            chunk_count=dup.chunk_count,
            is_duplicate=True,
            evidence_id=dup.evidence_id,
            record=dup,
            message=f"重复论文, 已存在 {dup.paper_id}",
        )

    paper_id = _make_paper_id("arxiv_download")
    raw_path = None
    if pdf_bytes:
        raw_path = storage.save_raw_pdf(project_id, arxiv_id or paper_id, pdf_bytes)

    # 切块
    chunks: list[PaperChunk] = []
    if full_text:
        chunks = chunker.chunk_text(
            full_text, paper_id=paper_id, project_id=project_id,
            title_hint=meta.get("title"),
        )
        # 保存 full text excerpt (前 5000 字)
        storage.save_full_text_excerpt(project_id, paper_id, full_text[:5000])

    record = PaperRecord(
        paper_id=paper_id,
        project_id=project_id,
        title=meta.get("title") or f"arXiv:{arxiv_id}",
        authors=meta.get("authors") or [],
        year=meta.get("year"),
        venue=None,
        doi=meta.get("doi"),
        arxiv_id=meta.get("arxiv_id") or arxiv_id,
        url=meta.get("url"),
        pdf_path=raw_path,
        sha256=sha,
        source_mode="arxiv_download",
        parse_status=parse_status,  # type: ignore[arg-type]
        page_count=page_count,
        chunk_count=len(chunks),
        metadata_status=metadata_status,  # type: ignore[arg-type]
    )
    _persist(record, chunks, sha)
    evidence_id = _link_evidence(record)
    if evidence_id:
        record.evidence_id = evidence_id
        storage.save_paper_record(record)

    return IngestOutcome(
        paper_id=paper_id,
        parse_status=parse_status,
        chunk_count=len(chunks),
        is_duplicate=False,
        evidence_id=evidence_id,
        record=record,
        message="arXiv 论文已入库",
    )


# ---------- 本地 PDF upload ingest ---------- #


def ingest_upload(
    project_id: str,
    filename: str,
    content_b64: str,
    mime: str | None = None,
) -> IngestOutcome:
    """本地 PDF base64 → bytes → sha256 → 解析 → 切块 → 落盘 → Evidence."""

    data = local_upload.decode_pdf_base64(content_b64)
    ok, msg = local_upload.validate_pdf_upload(filename, data, mime)
    if not ok:
        raise ValueError(msg)

    sha = local_upload.compute_sha256(data)

    # 解析全文
    parsed = pdf_parser.parse(data)
    full_text = parsed.get("text", "") or ""
    page_count = parsed.get("page_count", 0) or 0
    parse_status = parsed.get("status", "failed")  # parsed / skipped / failed

    # metadata
    meta = metadata_resolver.resolve_from_pdf_text(full_text)
    if not meta.get("title") or meta.get("title") == "untitled":
        meta["title"] = local_upload.derive_title_from_filename(filename)
    metadata_status = "resolved" if meta.get("title") and meta["title"] != "untitled" else "partial"

    # 重复检测
    existing_records = _load_existing_records(project_id)
    dup = dedup.find_duplicate(
        new_sha256=sha,
        new_doi=meta.get("doi"),
        new_arxiv_id=meta.get("arxiv_id"),
        new_title=meta.get("title"),
        new_year=meta.get("year"),
        existing=existing_records,
    )
    if dup:
        return IngestOutcome(
            paper_id=dup.paper_id,
            parse_status=dup.parse_status,
            chunk_count=dup.chunk_count,
            is_duplicate=True,
            evidence_id=dup.evidence_id,
            record=dup,
            message=f"重复论文 (sha256 命中), 已存在 {dup.paper_id}",
        )

    paper_id = _make_paper_id("local_upload")
    raw_path = storage.save_raw_pdf(project_id, sha[:8], data)

    # 切块
    chunks: list[PaperChunk] = []
    if full_text:
        chunks = chunker.chunk_text(
            full_text, paper_id=paper_id, project_id=project_id,
            title_hint=meta.get("title"),
        )
        storage.save_full_text_excerpt(project_id, paper_id, full_text[:5000])

    record = PaperRecord(
        paper_id=paper_id,
        project_id=project_id,
        title=meta.get("title"),
        authors=meta.get("authors") or [],
        year=meta.get("year"),
        venue=None,
        doi=meta.get("doi"),
        arxiv_id=meta.get("arxiv_id"),
        url=meta.get("url"),
        pdf_path=raw_path,
        sha256=sha,
        source_mode="local_upload",
        parse_status=parse_status,  # type: ignore[arg-type]
        page_count=page_count,
        chunk_count=len(chunks),
        metadata_status=metadata_status,  # type: ignore[arg-type]
    )
    _persist(record, chunks, sha)
    evidence_id = _link_evidence(record)
    if evidence_id:
        record.evidence_id = evidence_id
        storage.save_paper_record(record)

    return IngestOutcome(
        paper_id=paper_id,
        parse_status=parse_status,
        chunk_count=len(chunks),
        is_duplicate=False,
        evidence_id=evidence_id,
        record=record,
        message="PDF 已入库",
    )


# ---------- 查询 ---------- #


def _load_existing_records(project_id: str) -> list[PaperRecord]:
    out: list[PaperRecord] = []
    for pid in storage.list_paper_ids(project_id):
        rec = storage.load_record(project_id, pid)
        if rec is not None:
            out.append(rec)
    return out


def list_papers(project_id: str) -> list[PaperRecord]:
    return _load_existing_records(project_id)


def get_paper(project_id: str, paper_id: str) -> PaperRecord | None:
    return storage.load_record(project_id, paper_id)


def get_paper_chunks(project_id: str, paper_id: str) -> list[PaperChunk]:
    return storage.load_chunks(project_id, paper_id)


def get_paper_text_excerpt(project_id: str, paper_id: str) -> str:
    return storage.load_full_text(project_id, paper_id)


# ---------- 测试用: 重置 (单 project) ---------- #


def reset_project(project_id: str) -> None:
    """测试用: 清空某个 project 的 paper library 内存 + 文件."""

    import shutil
    from pathlib import Path
    root = Path(storage._library_root()) / storage._safe_project(project_id)
    if root.exists():
        shutil.rmtree(root)


__all__ = [
    "IngestOutcome",
    "ingest_arxiv",
    "ingest_upload",
    "list_papers",
    "get_paper",
    "get_paper_chunks",
    "get_paper_text_excerpt",
    "reset_project",
]
