"""资料摄入编排 (SOP §4 / §12 / §18)."""

from __future__ import annotations

import datetime as _dt
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from ...schemas_materials import (
    DraftCardUpdate,
    DraftEvidenceCard,
    DraftStatus,
    MaterialBuildCardsRequest,
    MaterialImportRequest,
    MaterialImportResponse,
    MaterialItem,
    MaterialParseStatus,
    MaterialTextRequest,
)
from .. import trace_store as _ts
from . import card_builder, dedup, image_parser, pdf_parser, storage, web_text_parser


# ---------- 状态 ---------- #

_LOCK = threading.RLock()
_MATERIALS: dict[str, list[MaterialItem]] = {}  # project_id -> materials
_DRAFTS: dict[str, list[DraftEvidenceCard]] = {}  # project_id -> drafts


def _materials(project_id: str) -> list[MaterialItem]:
    with _LOCK:
        return list(_MATERIALS.get(project_id, []))


def _drafts(project_id: str) -> list[DraftEvidenceCard]:
    with _LOCK:
        return list(_DRAFTS.get(project_id, []))


def _add_material(m: MaterialItem) -> None:
    with _LOCK:
        _MATERIALS.setdefault(m.project_id, []).append(m)


def _add_draft(d: DraftEvidenceCard) -> None:
    with _LOCK:
        _DRAFTS.setdefault(d.project_id, []).append(d)


def _replace_draft(d: DraftEvidenceCard) -> None:
    with _LOCK:
        arr = _DRAFTS.setdefault(d.project_id, [])
        for i, x in enumerate(arr):
            if x.draft_card_id == d.draft_card_id:
                arr[i] = d
                return
        arr.append(d)


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# ---------- 上传 ---------- #


def accept_upload(
    project_id: str,
    *,
    filename: str,
    data: bytes,
    mime: str | None = None,
    user_note: str | None = None,
    page_range: str | None = None,
    auto_build_cards: bool = True,
    preferred_type: str | None = None,
    material_id: str | None = None,
) -> dict[str, Any]:
    """接收上传, 保存 + 解析 + 生成草稿 (SOP §18.1).

    ``material_id`` 可由测试注入以与 ``pdf_parser.set_default_text`` 配对.
    """

    # 先做大 / MIME 校验, 但 material_id 可由调用方预生成
    if len(data) > storage.MAX_BYTES_DEFAULT:
        return {"error": f"文件过大 ({len(data)} > {storage.MAX_BYTES_DEFAULT} bytes)", "material": None, "draft_cards": []}

    safe_name = storage.sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    detected_mime = storage._guess_mime(safe_name, mime)
    ok, msg = storage.check_allowed(detected_mime, ext)
    if not ok:
        return {"error": msg, "material": None, "draft_cards": []}

    material_id = material_id or f"mat_{uuid.uuid4().hex[:10]}"
    safe_project = re.sub(r"[^\w\-]", "_", project_id)
    root = storage._storage_root() / safe_project / material_id
    root.mkdir(parents=True, exist_ok=True)

    storage_path = str(root / f"original{ext or '.bin'}")
    Path(storage_path).write_bytes(data)
    size_bytes = len(data)

    is_pdf = detected_mime == "application/pdf" or ext == "pdf"
    is_image = detected_mime.startswith("image/") if detected_mime else ext in {"png", "jpg", "jpeg", "webp"}

    parse_warnings: list[str] = []
    text_excerpt: str | None = None
    parse_status: MaterialParseStatus = "pending"
    parse_confidence: float | None = None
    page_count: int | None = None
    page_refs: list[str] = []
    parsed_payload: dict[str, Any] = {}

    if is_pdf:
        parsed = pdf_parser.parse_pdf(data, material_id=material_id)
        text_excerpt = (parsed.get("text") or "")[:1500] or None
        parse_status = parsed.get("status") or "skipped"
        parse_confidence = parsed.get("confidence")
        page_count = parsed.get("page_count") or 0
        page_refs = parsed.get("page_refs") or []
        parse_warnings = list(parsed.get("warnings") or [])
        parsed_payload = parsed
    elif is_image:
        parsed = image_parser.parse_image(storage_path, user_note=user_note, filename=filename)
        parse_status = parsed.get("status") or "parsed"
        parse_confidence = parsed.get("confidence")
        parse_warnings = list(parsed.get("warnings") or [])
        parsed_payload = parsed
    else:
        # 兜底: 文本 / markdown
        text_excerpt = data.decode("utf-8", errors="replace")[:1500] or None
        parse_status = "parsed"
        parse_confidence = 0.7
        parsed_payload = {
            "text": text_excerpt or "",
            "title": None,
            "summary": user_note or text_excerpt or filename,
            "suggested_type": "note",
            "extracted_claims": [],
            "possible_url": None,
            "possible_doi": None,
            "possible_arxiv_id": None,
            "page_refs": [],
            "confidence": 0.7,
            "warnings": [],
        }

    title_hint: str | None = None
    if is_pdf and parsed_payload:
        cand = pdf_parser.extract_paper_candidates(parsed_payload.get("text") or "")
        if cand.get("title"):
            title_hint = cand["title"]

    material = MaterialItem(
        material_id=material_id,
        project_id=project_id,
        source_type="pdf" if is_pdf else ("image" if is_image else "manual_note"),
        filename=storage.sanitize_filename(filename),
        original_url=None,
        title=title_hint,
        storage_path=storage_path,
        mime_type=detected_mime,
        size_bytes=size_bytes,
        text_excerpt=text_excerpt,
        page_count=page_count,
        page_range=page_range,
        created_at=_utcnow_iso(),
        parse_status=parse_status,
        parse_confidence=parse_confidence,
        parse_warnings=parse_warnings,
        user_note=user_note,
        metadata={"ext": ext, "is_pdf": is_pdf, "is_image": is_image},
    )
    _add_material(material)

    _ts.append_trace(
        project_id,
        action="material_uploaded",
        target_type="material",
        target_id=material_id,
        actor="user",
        after={
            "source_type": material.source_type,
            "mime": detected_mime,
            "size": size_bytes,
            "filename": material.filename,
        },
        reason=user_note or "",
    )
    if parse_status == "parsed":
        _ts.append_trace(
            project_id,
            action="material_parsed",
            target_type="material",
            target_id=material_id,
            actor="system",
            after={
                "page_count": page_count,
                "confidence": parse_confidence,
                "warnings": parse_warnings,
            },
        )
    elif parse_status == "failed":
        _ts.append_trace(
            project_id,
            action="material_parse_failed",
            target_type="material",
            target_id=material_id,
            actor="system",
            reason="; ".join(parse_warnings) or "parse failed",
        )

    drafts: list[DraftEvidenceCard] = []
    if auto_build_cards and parse_status in ("parsed", "skipped"):
        existing = _drafts(project_id)
        # 草稿: PDF 时根据候选走 paper; 图片走 note; 其它走 note
        if is_pdf and parsed_payload.get("text"):
            cand = pdf_parser.extract_paper_candidates(parsed_payload.get("text") or "")
            card_dict = card_builder.make_draft_card(
                project_id,
                material_id,
                {
                    "title": cand.get("title") or material.filename,
                    "summary": pdf_parser.extract_note_summary(parsed_payload.get("text") or "", user_note, max_len=1200),
                    "suggested_type": "paper" if (cand.get("doi") or cand.get("arxiv_id")) else "note",
                    "extracted_claims": [c for c in [cand.get("doi") and f"DOI: {cand['doi']}", cand.get("arxiv_id") and f"arXiv: {cand['arxiv_id']}"] if c],
                    "possible_url": cand.get("url"),
                    "possible_doi": cand.get("doi"),
                    "possible_arxiv_id": cand.get("arxiv_id"),
                    "page_refs": page_refs[:3],
                    "confidence": parse_confidence or 0.5,
                    "warnings": list(parse_warnings),
                    "source_excerpt": (parsed_payload.get("text") or "")[:500],
                },
                preferred_type=preferred_type,
            )
        elif is_image:
            card_dict = card_builder.make_draft_card(
                project_id,
                material_id,
                {
                    "title": material.filename or "图片资料",
                    "summary": parsed_payload.get("summary") or user_note or "图片资料 (无说明)",
                    "suggested_type": "note",
                    "extracted_claims": [],
                    "possible_url": None,
                    "page_refs": [],
                    "confidence": parse_confidence or 0.4,
                    "warnings": list(parse_warnings),
                },
                preferred_type=preferred_type,
            )
        else:
            card_dict = card_builder.make_draft_card(
                project_id,
                material_id,
                {
                    "title": material.filename or "文本资料",
                    "summary": parsed_payload.get("summary") or user_note or "",
                    "suggested_type": "note",
                    "extracted_claims": [],
                    "possible_url": None,
                    "page_refs": [],
                    "confidence": parse_confidence or 0.7,
                    "warnings": [],
                },
                preferred_type=preferred_type,
            )

        if not dedup.drafts_duplicate(card_dict, existing):
            card = DraftEvidenceCard(**card_dict)
            _add_draft(card)
            drafts.append(card)
            _ts.append_trace(
                project_id,
                action="draft_card_created",
                target_type="draft",
                target_id=card.draft_card_id,
                evidence_id=material_id,
                actor="system",
                after={
                    "suggested_type": card.suggested_type,
                    "title": card.title,
                    "confidence": card.extraction_confidence,
                },
            )

    return {
        "material": material,
        "draft_cards": drafts,
        "message": "" if parse_status == "parsed" else f"解析状态: {parse_status}",
    }


# ---------- 文本提交 ---------- #


def accept_text(
    project_id: str,
    body: MaterialTextRequest,
    auto_build_cards: bool = True,
    preferred_type: str | None = None,
) -> dict[str, Any]:
    """接收文本 / URL+描述 / 导师备注 (SOP §18.2)."""

    material_id = f"mat_{uuid.uuid4().hex[:10]}"
    text = body.text or ""
    if body.source_type == "manual_note":
        parsed = web_text_parser.parse_manual_note(text, user_note=body.user_note, title=body.title)
    elif body.source_type == "url_note":
        parsed = web_text_parser.parse_url_note(body.url or "", user_note=body.user_note, title=body.title)
    else:  # web_text
        parsed = web_text_parser.parse_web_text(text, url=body.url, user_note=body.user_note, title=body.title)

    parse_warnings: list[str] = list(parsed.get("warnings") or [])
    parse_status: MaterialParseStatus = "parsed" if (text or body.url or body.user_note) else "skipped"
    parse_confidence = parsed.get("confidence")
    if not text and not body.url and not body.user_note:
        parse_status = "skipped"
        parse_confidence = 0.0
        parse_warnings.append("无任何内容")

    material = MaterialItem(
        material_id=material_id,
        project_id=project_id,
        source_type=body.source_type,
        filename=None,
        original_url=body.url,
        title=parsed.get("title") or body.title,
        storage_path=None,
        mime_type="text/plain",
        size_bytes=len(text.encode("utf-8")) if text else None,
        text_excerpt=(text or "")[:1500] or None,
        page_count=0,
        page_range=None,
        created_at=_utcnow_iso(),
        parse_status=parse_status,
        parse_confidence=parse_confidence,
        parse_warnings=parse_warnings,
        user_note=body.user_note,
        metadata={"url": body.url},
    )
    _add_material(material)

    _ts.append_trace(
        project_id,
        action="material_text_submitted",
        target_type="material",
        target_id=material_id,
        actor="user",
        after={"source_type": body.source_type, "url": body.url, "len": len(text)},
        reason=body.user_note or "",
    )
    if parse_status == "parsed":
        _ts.append_trace(
            project_id,
            action="material_parsed",
            target_type="material",
            target_id=material_id,
            actor="system",
            after={"confidence": parse_confidence, "warnings": parse_warnings},
        )

    drafts: list[DraftEvidenceCard] = []
    if auto_build_cards and parse_status == "parsed":
        existing = _drafts(project_id)
        card_dict = card_builder.make_draft_card(
            project_id, material_id,
            {
                "title": parsed.get("title") or body.title or "网页资料",
                "summary": parsed.get("summary") or body.text[:800] or body.user_note or "",
                "suggested_type": parsed.get("suggested_type") or "note",
                "extracted_claims": parsed.get("extracted_claims") or [],
                "possible_url": parsed.get("possible_url"),
                "possible_doi": parsed.get("possible_doi"),
                "possible_arxiv_id": parsed.get("possible_arxiv_id"),
                "page_refs": [],
                "confidence": parsed.get("confidence") or 0.6,
                "warnings": parse_warnings,
                "source_excerpt": (text or body.user_note or "")[:500],
            },
            preferred_type=preferred_type,
        )
        if not dedup.drafts_duplicate(card_dict, existing):
            card = DraftEvidenceCard(**card_dict)
            _add_draft(card)
            drafts.append(card)
            _ts.append_trace(
                project_id,
                action="draft_card_created",
                target_type="draft",
                target_id=card.draft_card_id,
                evidence_id=material_id,
                actor="system",
                after={"suggested_type": card.suggested_type, "title": card.title},
            )

    return {"material": material, "draft_cards": drafts, "message": ""}


# ---------- 显式生成草稿 ---------- #


def build_draft_cards(
    project_id: str,
    material_id: str,
    request: MaterialBuildCardsRequest,
) -> list[DraftEvidenceCard]:
    """基于已有 material 再生成 1 张草稿 (SOP §18.3)."""

    mat = next((m for m in _materials(project_id) if m.material_id == material_id), None)
    if mat is None:
        return []
    existing = [d for d in _drafts(project_id) if d.material_id == material_id]

    # 1 张就够, 走 PDF 路径或文本路径
    if mat.source_type == "pdf" and mat.text_excerpt:
        cand = pdf_parser.extract_paper_candidates(mat.text_excerpt or "")
        card_dict = card_builder.make_draft_card(
            project_id, material_id,
            {
                "title": cand.get("title") or mat.title or mat.filename or "PDF 资料",
                "summary": pdf_parser.extract_note_summary(mat.text_excerpt or "", mat.user_note, max_len=1200),
                "suggested_type": "paper" if (cand.get("doi") or cand.get("arxiv_id")) else "note",
                "extracted_claims": [c for c in [cand.get("doi") and f"DOI: {cand['doi']}", cand.get("arxiv_id") and f"arXiv: {cand['arxiv_id']}"] if c],
                "possible_url": cand.get("url"),
                "possible_doi": cand.get("doi"),
                "possible_arxiv_id": cand.get("arxiv_id"),
                "page_refs": [],
                "confidence": mat.parse_confidence or 0.6,
                "warnings": list(mat.parse_warnings),
                "source_excerpt": (mat.text_excerpt or "")[:500],
            },
            preferred_type=request.preferred_type,
        )
    elif mat.source_type in ("image", "screenshot"):
        card_dict = card_builder.make_draft_card(
            project_id, material_id,
            {
                "title": mat.filename or "图片资料",
                "summary": mat.user_note or "图片资料",
                "suggested_type": "note",
                "page_refs": [],
                "confidence": mat.parse_confidence or 0.4,
                "warnings": list(mat.parse_warnings),
            },
            preferred_type=request.preferred_type,
        )
    else:
        text = mat.text_excerpt or ""
        parsed = web_text_parser.parse_web_text(text, url=mat.original_url, user_note=mat.user_note, title=mat.title)
        card_dict = card_builder.make_draft_card(
            project_id, material_id,
            {
                "title": parsed.get("title") or mat.title or "资料",
                "summary": parsed.get("summary") or mat.user_note or text[:800],
                "suggested_type": parsed.get("suggested_type") or "note",
                "extracted_claims": parsed.get("extracted_claims") or [],
                "possible_url": parsed.get("possible_url"),
                "possible_doi": parsed.get("possible_doi"),
                "possible_arxiv_id": parsed.get("possible_arxiv_id"),
                "page_refs": [],
                "confidence": parsed.get("confidence") or 0.6,
                "warnings": list(mat.parse_warnings),
                "source_excerpt": (text or mat.user_note or "")[:500],
            },
            preferred_type=request.preferred_type,
        )

    if dedup.drafts_duplicate(card_dict, existing):
        return []
    card = DraftEvidenceCard(**card_dict)
    _add_draft(card)
    _ts.append_trace(
        project_id,
        action="draft_card_created",
        target_type="draft",
        target_id=card.draft_card_id,
        evidence_id=material_id,
        actor="user",
        after={"suggested_type": card.suggested_type, "title": card.title},
    )
    return [card]


# ---------- 草稿编辑 ---------- #


def edit_draft_card(project_id: str, draft_card_id: str, body: DraftCardUpdate) -> DraftEvidenceCard | None:
    drafts = _drafts(project_id)
    for d in drafts:
        if d.draft_card_id == draft_card_id:
            data = d.model_dump()
            changed = False
            for k in ("title", "summary", "suggested_type", "possible_url", "possible_doi", "possible_arxiv_id", "status"):
                v = getattr(body, k)
                if v is not None and v != data.get(k):
                    data[k] = v
                    changed = True
            if body.user_note is not None:
                data["warnings"] = list(data.get("warnings") or [])
                if body.user_note:
                    data["warnings"].append(f"user_note: {body.user_note}")
                changed = True
            if changed:
                data["updated_at"] = _utcnow_iso()
                if data.get("status") == "imported":
                    pass  # 已导入, 不再改
                else:
                    data["status"] = "edited"
                nd = DraftEvidenceCard(**data)
                _replace_draft(nd)
                _ts.append_trace(
                    project_id,
                    action="draft_card_edited",
                    target_type="draft",
                    target_id=draft_card_id,
                    evidence_id=nd.material_id,
                    actor="user",
                    before=d.model_dump(),
                    after=nd.model_dump(),
                )
                return nd
            return d
    return None


# ---------- 列表 / 单查 ---------- #


def list_materials(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "materials": _materials(project_id),
        "drafts": _drafts(project_id),
    }


def get_material(project_id: str, material_id: str) -> MaterialItem | None:
    for m in _materials(project_id):
        if m.material_id == material_id:
            return m
    return None


def get_summary(project_id: str) -> dict[str, Any]:
    mats = _materials(project_id)
    drafts = _drafts(project_id)
    by_type: dict[str, int] = {}
    for m in mats:
        by_type[m.source_type] = by_type.get(m.source_type, 0) + 1
    return {
        "project_id": project_id,
        "total_materials": len(mats),
        "total_drafts": len(drafts),
        "by_source_type": by_type,
        "parsed_materials": sum(1 for m in mats if m.parse_status == "parsed"),
        "skipped_materials": sum(1 for m in mats if m.parse_status == "skipped"),
        "failed_materials": sum(1 for m in mats if m.parse_status == "failed"),
        "imported_drafts": sum(1 for d in drafts if d.status == "imported"),
    }


# ---------- 导入 Evidence Ledger ---------- #


def import_drafts(project_id: str, request: MaterialImportRequest) -> MaterialImportResponse:
    """把选中的 draft 写入 Evidence Ledger (SOP §12)."""

    drafts = _drafts(project_id)
    by_id = {d.draft_card_id: d for d in drafts}

    selected: list[DraftEvidenceCard] = []
    if request.draft_card_ids:
        for did in request.draft_card_ids:
            d = by_id.get(did)
            if d is not None and d.status not in ("imported", "rejected"):
                selected.append(d)
    else:
        # 默认: 所有 status != imported/rejected
        selected = [d for d in drafts if d.status not in ("imported", "rejected")]

    if not selected:
        return MaterialImportResponse(
            imported=0, skipped=0, evidence_ids=[], skipped_draft_ids=[],
            message="无可导入的草稿",
        )

    from .. import evidence as _ev

    imported_ids: list[str] = []
    skipped_draft_ids: list[str] = []
    warnings: list[str] = []

    # ledger dedup
    ledger = _ev.get_ledger(project_id)
    ledger_items = [*ledger.papers, *ledger.datasets, *ledger.repos, *ledger.notes]

    for d in selected:
        if dedup.is_duplicate_in_ledger(d.model_dump(), ledger_items):
            skipped_draft_ids.append(d.draft_card_id)
            _ts.append_trace(
                project_id,
                action="draft_card_rejected",
                target_type="draft",
                target_id=d.draft_card_id,
                evidence_id=d.material_id,
                actor="system",
                reason="已存在于 Evidence Ledger",
            )
            continue

        eid = _build_evidence_from_draft(project_id, d, request.workspace_lane)
        if eid is None:
            skipped_draft_ids.append(d.draft_card_id)
            warnings.append(f"{d.draft_card_id}: 类型不匹配或创建失败")
            continue
        imported_ids.append(eid)
        # 标记为 imported
        new_data = d.model_dump()
        new_data["status"] = "imported"
        new_data["updated_at"] = _utcnow_iso()
        _replace_draft(DraftEvidenceCard(**new_data))
        _ts.append_trace(
            project_id,
            action="draft_card_imported",
            target_type="evidence",
            target_id=eid,
            evidence_id=eid,
            actor="user",
            before={"draft_card_id": d.draft_card_id, "title": d.title},
            after={
                "suggested_type": d.suggested_type,
                "workspace_lane": request.workspace_lane,
                "created_by_skill": card_builder.skill_for_type(d.suggested_type),
                "review_status": "pending",
            },
            reason=d.summary[:120] if d.summary else "",
        )

    # 可选 auto_verify
    verified_count = 0
    if request.auto_verify and imported_ids:
        try:
            from .. import verification as _ver

            for eid in imported_ids:
                item = _ev.get_item(eid)
                if item is None:
                    continue
                result = _ver.verify_evidence_item(item)
                updated = _ver.apply_verification(item, result)
                try:
                    _ev.update_verification_field(eid, updated)
                    verified_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    msg = f"已导入 {len(imported_ids)} 张草稿"
    if verified_count:
        msg += f", 自动验证 {verified_count} 条"
    return MaterialImportResponse(
        imported=len(imported_ids),
        skipped=len(skipped_draft_ids),
        evidence_ids=imported_ids,
        skipped_draft_ids=skipped_draft_ids,
        warnings=warnings,
        message=msg,
    )


def _build_evidence_from_draft(project_id: str, d: DraftEvidenceCard, workspace_lane: str) -> str | None:
    """把草稿写入 Evidence Ledger."""

    from .. import evidence as _ev
    from ...schemas_evidence import (
        DatasetManualCreate,
        PaperManualCreate,
        RepoManualCreate,
    )

    try:
        page_refs = list(d.page_refs or [])[:3]
        if d.suggested_type == "paper":
            body = PaperManualCreate(
                title=d.title or "未命名 PDF 资料",
                authors=[],
                year=None,
                url=d.possible_url,
                doi=d.possible_doi,
                arxiv_id=d.possible_arxiv_id,
                abstract=d.summary,
                user_note=d.summary[:200] if d.summary else None,
                tags=["material", d.material_id, d.draft_card_id],
                review_status="pending",
            )
            resp = _ev.add_paper_manual(project_id, body)
            if not resp.ok:
                return None
            _post_import_patch(
                resp.evidence_id,
                source_mode="upload", workspace_lane=workspace_lane,
                skill=card_builder.skill_for_type("paper"),
                from_material_id=d.material_id,
                parse_confidence=d.extraction_confidence,
                page_refs=page_refs,
            )
            return resp.evidence_id

        if d.suggested_type == "dataset":
            body = DatasetManualCreate(
                name=d.title or "未命名数据集",
                scale=None,
                license=None,
                download=d.possible_url,
                modality=[],
                annotation=d.summary[:200] if d.summary else None,
                user_note=d.summary[:200] if d.summary else None,
                review_status="pending",
            )
            resp = _ev.add_dataset_manual(project_id, body)
            if not resp.ok:
                return None
            _post_import_patch(
                resp.evidence_id,
                source_mode="upload", workspace_lane=workspace_lane,
                skill=card_builder.skill_for_type("dataset"),
                from_material_id=d.material_id,
                parse_confidence=d.extraction_confidence,
                page_refs=page_refs,
            )
            return resp.evidence_id

        if d.suggested_type == "repo":
            body = RepoManualCreate(
                name=d.title or "未命名仓库",
                repository_url=d.possible_url,
                paper_title=None,
                license=None,
                has_readme=False,
                has_env_file=False,
                has_training_script=False,
                has_eval_script=False,
                user_note=d.summary[:200] if d.summary else None,
                review_status="pending",
            )
            resp = _ev.add_repo_manual(project_id, body)
            if not resp.ok:
                return None
            _post_import_patch(
                resp.evidence_id,
                source_mode="upload", workspace_lane=workspace_lane,
                skill=card_builder.skill_for_type("repo"),
                from_material_id=d.material_id,
                parse_confidence=d.extraction_confidence,
                page_refs=page_refs,
            )
            return resp.evidence_id

        # note / custom 走 paper 通道 (note 通道暂未独立)
        body = PaperManualCreate(
            title=d.title or "导师备注",
            url=None,
            year=None,
            abstract=None,
            user_note=d.summary,
            tags=["material", "note", d.material_id, d.draft_card_id],
            review_status="pending",
        )
        resp = _ev.add_paper_manual(project_id, body)
        if not resp.ok:
            return None
        _post_import_patch(
            resp.evidence_id,
            source_mode="upload", workspace_lane=workspace_lane,
            skill=card_builder.skill_for_type("note"),
            from_material_id=d.material_id,
            parse_confidence=d.extraction_confidence,
            page_refs=page_refs,
        )
        return resp.evidence_id
    except Exception:
        return None


def _post_import_patch(
    evidence_id: str,
    *,
    source_mode: str,
    workspace_lane: str,
    skill: str,
    from_material_id: str | None = None,
    parse_confidence: float | None = None,
    page_refs: list[str] | None = None,
) -> None:
    """import 后修改 source_mode / workspace_lane / created_by_skill."""

    from .. import evidence as _ev
    from ...schemas_evidence import EvidenceItem

    item = _ev.get_item(evidence_id)
    if item is None:
        return
    new_data = item.model_dump()
    new_data["source_mode"] = source_mode
    new_data["workspace_lane"] = workspace_lane
    new_data["created_by_skill"] = skill
    new_data["verification_status"] = "unverified"
    new_data["verification_source"] = "none"
    new_data["verification_confidence"] = None
    new_data["verification_checked_at"] = None
    new_data["verification_warnings"] = []
    new_data["verification_metadata"] = {}
    new_data["url_verified"] = False
    new_data["raw_input_ref"] = evidence_id
    if from_material_id is not None:
        new_data["from_material_id"] = from_material_id
    if parse_confidence is not None:
        new_data["parse_confidence"] = parse_confidence
    if page_refs is not None:
        new_data["page_refs"] = list(page_refs)
    from .. import evidence as _ev2
    with _ev2._LEDGER_LOCK:  # type: ignore[attr-defined]
        for proj in _ev2._LEDGER.values():  # type: ignore[attr-defined]
            if evidence_id in proj.items:
                proj.items[evidence_id] = EvidenceItem(**new_data)
                return


# ---------- 测试用 ---------- #


def reset_materials_state() -> None:
    """清空所有 materials / drafts (测试用)."""

    global _MATERIALS, _DRAFTS
    with _LOCK:
        _MATERIALS = {}
        _DRAFTS = {}
    pdf_parser.clear_default_text()