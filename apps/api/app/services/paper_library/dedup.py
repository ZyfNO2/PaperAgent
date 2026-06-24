"""Paper Library dedup (Session 46 §8).

四类规则:
1. arXiv 下载: arxiv_id 完全相同
2. 本地上传: sha256 相同
3. 跨类型: DOI 相同
4. 标题 jaccard > 0.92

返回已有 paper_id (或 None).
"""

from __future__ import annotations

import re
from typing import Iterable

from ...schemas_paper_library import PaperRecord


def _norm_title(t: str) -> str:
    """标题归一化: 小写 + 去标点 + 合并空白."""

    t = (t or "").lower().strip()
    t = re.sub(r"[\s\W_]+", " ", t)
    return t.strip()


def _jaccard(a: str, b: str) -> float:
    """词级 jaccard 相似度."""

    sa = set(_norm_title(a).split())
    sb = set(_norm_title(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_duplicate(
    *,
    new_sha256: str | None,
    new_doi: str | None,
    new_arxiv_id: str | None,
    new_title: str,
    new_year: int | None,
    existing: Iterable[PaperRecord],
) -> PaperRecord | None:
    """返回已存在的重复 PaperRecord (None 表示无重复)."""

    new_doi_n = (new_doi or "").strip().lower() or None
    new_arxiv_n = (new_arxiv_id or "").strip().lower() or None
    new_title_n = _norm_title(new_title)
    new_sha = (new_sha256 or "").strip().lower() or None

    for e in existing:
        # 1. sha256
        if new_sha and e.sha256 and e.sha256.lower() == new_sha:
            return e
        # 2. arxiv_id
        if new_arxiv_n and e.arxiv_id and e.arxiv_id.lower() == new_arxiv_n:
            return e
        # 3. doi
        if new_doi_n and e.doi and e.doi.lower() == new_doi_n:
            return e
        # 4. 标题 jaccard
        if new_title_n and e.title:
            et = _norm_title(e.title)
            # 年份过滤: 双方年份已知且不同 → 不视作重复
            if e.year is not None and new_year is not None and e.year != new_year:
                continue
            if et == new_title_n:
                return e
            if _jaccard(et, new_title_n) > 0.92:
                return e
    return None
