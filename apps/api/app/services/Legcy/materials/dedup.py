"""草稿 / 资料 dedup."""

from __future__ import annotations

from typing import Iterable


def _norm_title(t: str | None) -> str:
    if not t:
        return ""
    import re

    s = t.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200]


def drafts_duplicate(new: dict, existing: Iterable) -> str | None:
    """检测新 draft 是否与已有 draft 重复 (同 material_id + 标题近相同)."""

    nt = _norm_title(new.get("title"))
    if not nt:
        return None
    mid = new.get("material_id")
    new_id = new.get("draft_card_id")
    for ex in existing:
        ex_id = getattr(ex, "draft_card_id", None)
        if ex_id == new_id:
            continue
        ex_mid = getattr(ex, "material_id", None)
        ex_title = getattr(ex, "title", None)
        if ex_mid == mid and _norm_title(ex_title) == nt:
            return ex_id
    return None


def is_duplicate_in_ledger(new: dict, ledger_items: Iterable) -> bool:
    """检查导入后是否与 ledger 中已有 evidence 重复 (按 DOI / arXiv / URL)."""

    candidates = []
    if new.get("possible_doi"):
        candidates.append(("doi", new["possible_doi"].lower().strip()))
    if new.get("possible_arxiv_id"):
        candidates.append(("arxiv", new["possible_arxiv_id"].lower().strip()))
    if new.get("possible_url"):
        from urllib.parse import urlparse

        u = urlparse(new["possible_url"])
        if u.netloc:
            candidates.append(("url", f"{u.scheme.lower()}://{u.netloc.lower()}{u.path.rstrip('/')}"))

    if not candidates:
        return False
    for it in ledger_items:
        for kind, val in candidates:
            if kind == "doi" and getattr(it, "doi", None) and it.doi.lower().strip() == val:
                return True
            if kind == "arxiv" and getattr(it, "arxiv_id", None) and it.arxiv_id.lower().strip() == val:
                return True
            if kind == "url" and getattr(it, "url", None):
                from urllib.parse import urlparse as _up

                uu = _up(it.url)
                if uu.netloc:
                    nv = f"{uu.scheme.lower()}://{uu.netloc.lower()}{uu.path.rstrip('/')}"
                    if nv == val:
                        return True
    return False