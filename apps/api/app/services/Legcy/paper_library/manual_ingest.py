"""Session 60 M1: ManualPaperIngest.

用户手动提交文献标题 + 文本 (粘贴摘要 / 笔记 / 整段文字)
→ PaperRecord + PaperChunk → 写入 paper_library.storage.

该模块**不**做:
- 不调用外部搜索 (那是 arxiv_downloader 的事)
- 不做 RAG 问答 (那是 local_rag.ask)
- 不写前端状态
- 不重复实现 storage / chunker

最低输入: { title, text, url?, tags? }
最低输出: { paper_id, status, parse_status, chunk_count, is_duplicate, message }
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from ...schemas_paper_library import PaperChunk, PaperRecord, ParseStatus, SourceMode
from . import chunker, dedup, storage

logger = logging.getLogger(__name__)


@dataclass
class ManualIngestOutcome:
    paper_id: str
    status: str  # "ingested" / "duplicate" / "failed"
    parse_status: ParseStatus
    chunk_count: int
    is_duplicate: bool
    message: str = ""


def _make_paper_id() -> str:
    """manual 来源用 mn 前缀 (区别于 ax / up)."""

    return f"paper_mn_{uuid.uuid4().hex[:10]}"


def _load_existing_records(project_id: str) -> list[PaperRecord]:
    out: list[PaperRecord] = []
    for pid in storage.list_paper_ids(project_id):
        rec = storage.load_record(project_id, pid)
        if rec is not None:
            out.append(rec)
    return out


def _find_dup_by_title(project_id: str, title: str) -> PaperRecord | None:
    """简易去重: 标题归一化后精确匹配.

    用户手输的 text 没有 sha256/arXiv ID, 只能靠标题判断.
    标题归一化: 去标点 / 去多余空白 / 转小写.
    """

    norm = _normalize_title(title)
    if not norm:
        return None
    for rec in _load_existing_records(project_id):
        if _normalize_title(rec.title) == norm:
            return rec
    return None


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    s = title.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w一-鿿 ]+", "", s)
    return s.strip()


def ingest_manual_text(
    project_id: str,
    title: str,
    text: str,
    url: str | None = None,
    tags: list[str] | None = None,
) -> ManualIngestOutcome:
    """手动入库: title + 纯文本 → PaperRecord + PaperChunk.

    流程:
    1. 校验 title / text 非空 (text 至少 10 字)
    2. 去重 (按标题归一化)
    3. 切块 (复用 chunker.chunk_text)
    4. 落盘 (storage.save_paper_record / save_chunks / update_manifest)
    5. 返回 outcome (不入 Evidence Ledger — manual 来源由 SOP §5 显式走 evidence.add_paper_manual)
    """

    if not title or not title.strip():
        return ManualIngestOutcome(
            paper_id="",
            status="failed",
            parse_status="failed",
            chunk_count=0,
            is_duplicate=False,
            message="title 不能为空",
        )
    if not text or not text.strip() or len(text.strip()) < 10:
        return ManualIngestOutcome(
            paper_id="",
            status="failed",
            parse_status="failed",
            chunk_count=0,
            is_duplicate=False,
            message="text 至少 10 字",
        )

    # 去重
    dup = _find_dup_by_title(project_id, title)
    if dup:
        return ManualIngestOutcome(
            paper_id=dup.paper_id,
            status="duplicate",
            parse_status=dup.parse_status,
            chunk_count=dup.chunk_count,
            is_duplicate=True,
            message=f"标题重复, 已存在 {dup.paper_id}",
        )

    paper_id = _make_paper_id()

    # 切块
    try:
        chunks: list[PaperChunk] = chunker.chunk_text(
            text, paper_id=paper_id, project_id=project_id,
            title_hint=title,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("manual chunk_text failed: %s", exc)
        chunks = []

    parse_status: ParseStatus = "parsed" if chunks else "skipped"

    record = PaperRecord(
        paper_id=paper_id,
        project_id=project_id,
        title=title.strip(),
        authors=[],
        year=None,
        venue=None,
        doi=None,
        arxiv_id=None,
        url=(url.strip() if url and url.strip() else None),
        pdf_path=None,
        sha256=None,
        source_mode="manual",  # type: ignore[arg-type]
        parse_status=parse_status,
        page_count=0,
        chunk_count=len(chunks),
        metadata_status="partial",
    )

    # 落盘
    record_path = storage.save_paper_record(record)
    chunks_path = storage.save_chunks(chunks) if chunks else ""
    storage.update_manifest(
        project_id=project_id,
        paper_id=paper_id,
        record_path=record_path,
        chunks_path=chunks_path,
        chunk_count=len(chunks),
        parse_status=parse_status,
        source_mode="manual",
        sha256=None,
        arxiv_id=None,
    )
    # ponytail: 不调 storage.save_full_text_excerpt —— 它会把 full_text_excerpt 字段写回
    # parsed JSON, 与 PaperRecord.extra="forbid" 冲突 (storage.py 预存在的 latent bug).
    # manual 来源的全文在 chunks 里已经完整保留, 不需要再保存 excerpt.

    return ManualIngestOutcome(
        paper_id=paper_id,
        status="ingested",
        parse_status=parse_status,
        chunk_count=len(chunks),
        is_duplicate=False,
        message=f"manual 文本已入库 ({len(chunks)} chunks)",
    )


__all__ = ["ingest_manual_text", "ManualIngestOutcome"]