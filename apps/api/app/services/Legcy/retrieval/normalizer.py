"""候选归一化: 不同 source 的原始 dict -> RetrievalCandidate (SOP §9)."""

from __future__ import annotations

from typing import Any

from ...schemas_retrieval import CandidateType, RetrievalCandidate, SearchSource


_SOURCE_TO_TYPE: dict[SearchSource, CandidateType] = {
    "openalex": "paper",
    "crossref": "paper",
    "semantic_scholar": "paper",
    "arxiv": "paper",
    "github": "repo",
    "huggingface": "dataset",
    "kaggle": "dataset",
    "manual_fallback": "note",
}


def _reconstruct_abstract(inverted_index: Any) -> str | None:
    """OpenAlex abstract_inverted_index -> text.

    形如 ``{"word": [pos1, pos2]}`` -> "word at pos".
    """

    if not isinstance(inverted_index, dict):
        if isinstance(inverted_index, str):
            return inverted_index or None
        return None
    pos_to_word: dict[int, str] = {}
    for word, positions in inverted_index.items():
        if not isinstance(positions, list):
            continue
        for p in positions:
            try:
                pos_to_word[int(p)] = word
            except (TypeError, ValueError):
                continue
    if not pos_to_word:
        return None
    max_pos = max(pos_to_word.keys())
    parts: list[str] = []
    for i in range(max_pos + 1):
        parts.append(pos_to_word.get(i, ""))
    text = " ".join(parts).strip()
    return text or None


def _clean_str(s: Any, *, max_len: int = 1000) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def _extract_license(raw: dict) -> str | None:
    """从 raw 抽取 license 字符串 (GitHub license 可能是 dict)."""

    lic = raw.get("license")
    if isinstance(lic, str):
        return lic or None
    if isinstance(lic, dict):
        for k in ("spdx_id", "name", "key"):
            v = lic.get(k)
            if v:
                return str(v)
    # 别名字段
    for k in ("license_name", "spdx_id"):
        v = raw.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _parse_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _extract_authors_openalex(raw: dict) -> list[str]:
    out: list[str] = []
    for a in raw.get("authorships") or []:
        if isinstance(a, dict):
            au = a.get("author") or {}
            name = au.get("display_name") if isinstance(au, dict) else None
            if name:
                out.append(str(name))
    return out


def _extract_authors_s2(raw: dict) -> list[str]:
    out: list[str] = []
    for a in raw.get("authors") or []:
        if isinstance(a, dict):
            n = a.get("name")
            if n:
                out.append(str(n))
        elif isinstance(a, str):
            out.append(a)
    return out


def _extract_venue_openalex(raw: dict) -> str | None:
    loc = raw.get("primary_location") or {}
    src = loc.get("source") or {} if isinstance(loc, dict) else {}
    if isinstance(src, dict):
        v = src.get("display_name")
        if v:
            return str(v)
    return None


def normalize_candidate(
    raw: dict,
    *,
    project_id: str,
    source: SearchSource,
    candidate_id: str,
) -> RetrievalCandidate:
    """把 source-specific dict 归一化为 ``RetrievalCandidate``.

    字段缺失不会报错, 缺则留空. type 由 source 决定, 也可被 raw 覆盖.
    """

    if not isinstance(raw, dict):
        raw = {"title": str(raw)}

    candidate_type: CandidateType = raw.get("_candidate_type") or _SOURCE_TO_TYPE.get(source, "note")
    title = _clean_str(raw.get("title") or raw.get("name") or raw.get("full_name") or "")
    # HuggingFace / Kaggle 数据集可能只有 id, 用 slug 兜底标题
    if not title:
        slug = raw.get("id") or raw.get("dataset_slug") or raw.get("full_name")
        if isinstance(slug, str) and slug:
            title = slug.split("/")[-1].replace("-", " ").replace("_", " ")

    cand = RetrievalCandidate(
        candidate_id=candidate_id,
        project_id=project_id,
        candidate_type=candidate_type,
        source=source,
        title=title,
        url=raw.get("url") or raw.get("html_url") or raw.get("doi_url"),
        year=_parse_int(raw.get("year") or raw.get("publication_year")),
        doi=raw.get("doi"),
        arxiv_id=raw.get("arxiv_id") or raw.get("arxiv"),
        openalex_id=str(raw.get("openalex_id") or raw.get("id") or "") or None,
        semantic_scholar_id=raw.get("semantic_scholar_id") or raw.get("paperId"),
        repo_full_name=raw.get("full_name") or raw.get("repo_full_name"),
        dataset_slug=raw.get("dataset_slug") or (str(raw.get("id")) if raw.get("id") else None),
        license=_extract_license(raw),
        stars=_parse_int(raw.get("stars") or raw.get("stargazers_count")),
        citation_count=_parse_int(raw.get("citation_count") or raw.get("cited_by_count")),
        updated_at=raw.get("updated_at") or raw.get("lastModified"),
        raw=raw,
    )

    # 类型特定字段
    if source in ("openalex", "semantic_scholar", "arxiv"):
        cand.authors = (
            _extract_authors_openalex(raw)
            if source == "openalex"
            else _extract_authors_s2(raw)
        )
        cand.abstract = (
            _reconstruct_abstract(raw.get("abstract_inverted_index"))
            if source == "openalex"
            else (raw.get("abstract") if isinstance(raw.get("abstract"), str) else None)
        )
        if source == "openalex":
            cand.venue = _extract_venue_openalex(raw)
        elif source == "arxiv":
            cand.venue = "arXiv"
        # arXiv 缺 year 时从 published 取
        if source == "arxiv" and cand.year is None:
            pub = raw.get("published") or raw.get("updated")
            if isinstance(pub, str) and len(pub) >= 4 and pub[:4].isdigit():
                cand.year = int(pub[:4])

    if source == "github":
        cand.abstract = raw.get("description") if isinstance(raw.get("description"), str) else None
        topics = raw.get("topics") or []
        if isinstance(topics, list):
            for t in topics:
                if isinstance(t, dict) and t.get("name"):
                    cand.quality_hints.append(f"topic:{t['name']}")

    if source in ("huggingface", "kaggle"):
        if source == "huggingface":
            card = raw.get("cardData") or {}
            if isinstance(card, dict):
                ds_info = card.get("dataset_info") or {}
                if isinstance(ds_info, dict):
                    desc = ds_info.get("description")
                    if isinstance(desc, str) and not cand.abstract:
                        cand.abstract = desc
                tags = card.get("tags")
                if isinstance(tags, list):
                    for t in tags:
                        if isinstance(t, str):
                            cand.quality_hints.append(f"tag:{t}")
        # likes/downloads 当成 quality_hints
        for k, label in (("likes", "likes"), ("downloads", "downloads")):
            v = raw.get(k)
            if v is not None:
                cand.quality_hints.append(f"{label}:{v}")

    return cand
