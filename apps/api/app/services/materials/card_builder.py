"""DraftEvidenceCard 生成 (SOP §8.3 / §9.3 / §10.2 / §11)."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any


_SKILL_BY_TYPE = {
    "paper": "paper-card",
    "dataset": "dataset-validation",
    "repo": "github-baseline",
    "note": "evidence-ledger",
    "custom": "evidence-ledger",
}


def make_draft_card(
    project_id: str,
    material_id: str,
    parsed: dict[str, Any],
    *,
    preferred_type: str | None = None,
) -> dict[str, Any]:
    """从解析结果 dict 生成 1 张草稿 card (dict, 调用方负责 model_validate)."""

    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    suggested = parsed.get("suggested_type") or "note"
    if preferred_type and preferred_type in _SKILL_BY_TYPE:
        suggested = preferred_type
    card: dict[str, Any] = {
        "draft_card_id": f"draft_{uuid.uuid4().hex[:10]}",
        "project_id": project_id,
        "material_id": material_id,
        "suggested_type": suggested,
        "title": parsed.get("title") or "未命名资料",
        "summary": parsed.get("summary") or "",
        "extracted_claims": list(parsed.get("extracted_claims") or []),
        "extracted_entities": list(parsed.get("extracted_entities") or []),
        "possible_url": parsed.get("possible_url"),
        "possible_doi": parsed.get("possible_doi"),
        "possible_arxiv_id": parsed.get("possible_arxiv_id"),
        "source_excerpt": parsed.get("source_excerpt"),
        "page_refs": list(parsed.get("page_refs") or []),
        "extraction_confidence": float(parsed.get("confidence") or 0.0),
        "warnings": list(parsed.get("warnings") or []),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    return card


def skill_for_type(suggested_type: str) -> str:
    return _SKILL_BY_TYPE.get(suggested_type, "evidence-ledger")