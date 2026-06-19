"""候选去重 (SOP §10)."""

from __future__ import annotations

from typing import Iterable

from ...schemas_retrieval import RetrievalCandidate
from ._http import normalize_url, normalize_title, title_similarity


def _doi_key(c: RetrievalCandidate) -> str | None:
    if not c.doi:
        return None
    return c.doi.strip().lower()


def _arxiv_key(c: RetrievalCandidate) -> str | None:
    if not c.arxiv_id:
        return None
    a = c.arxiv_id.strip().lower()
    for prefix in ("arxiv:", "arXiv:"):
        if a.startswith(prefix):
            a = a[len(prefix):]
    return a


def _openalex_key(c: RetrievalCandidate) -> str | None:
    if not c.openalex_id:
        return None
    return c.openalex_id.strip()


def _s2_key(c: RetrievalCandidate) -> str | None:
    if not c.semantic_scholar_id:
        return None
    return c.semantic_scholar_id.strip()


def _repo_key(c: RetrievalCandidate) -> str | None:
    if c.repo_full_name:
        return c.repo_full_name.strip().lower()
    if c.url and "github.com" in c.url.lower():
        # 从 URL 抽取 owner/repo
        from urllib.parse import urlparse

        u = urlparse(c.url)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0].lower()}/{parts[1].lower().rstrip('.git')}"
    return None


def _dataset_key(c: RetrievalCandidate) -> str | None:
    if c.dataset_slug:
        return c.dataset_slug.strip().lower()
    return normalize_url(c.url)


def _url_key(c: RetrievalCandidate) -> str | None:
    return normalize_url(c.url)


def _candidate_fingerprint(c: RetrievalCandidate) -> set[str]:
    """返回候选的所有强 fingerprint (DOI / arXiv / openalex / s2 / repo / dataset / url)."""

    keys: set[str] = set()
    for fn in (
        _doi_key,
        _arxiv_key,
        _openalex_key,
        _s2_key,
        _repo_key,
        _dataset_key,
        _url_key,
    ):
        k = fn(c)
        if k:
            keys.add(f"{fn.__name__}:{k}")
    return keys


def _title_year_cluster_key(c: RetrievalCandidate) -> str | None:
    title = normalize_title(c.title)
    if not title or c.year is None:
        return None
    return f"{title}::{c.year}"


def dedup_candidates(
    candidates: list[RetrievalCandidate],
    *,
    paper_title_threshold: float = 0.92,
    dataset_title_threshold: float = 0.90,
) -> list[RetrievalCandidate]:
    """按 SOP §10 规则去重.

    规则顺序:
    1. 强指纹命中 (DOI/arXiv/OpenAlex/S2/repo/dataset/url) -> duplicate
    2. 论文: 同 normalized_title + 同 year + similarity > threshold -> duplicate
    3. 数据集: 同 url/slug/title-similarity > threshold -> duplicate
    4. repo: 同 owner/name -> duplicate
    """

    out: list[RetrievalCandidate] = []
    seen_fps: list[set[str]] = []
    title_year_keys: list[tuple[str, int, str] | None] = []  # (normalized_title, year, candidate_type)

    for c in candidates:
        fp = _candidate_fingerprint(c)
        title_year_key: tuple[str, int, str] | None = None
        if c.candidate_type == "paper":
            nt = normalize_title(c.title)
            if nt and c.year is not None:
                title_year_key = (nt, c.year, "paper")
        elif c.candidate_type == "dataset":
            nt = normalize_title(c.title)
            if nt:
                title_year_key = (nt, c.year or 0, "dataset")

        dup_of: str | None = None

        # 1) 强指纹
        for i, other_fp in enumerate(seen_fps):
            if fp and fp & other_fp:
                dup_of = out[i].candidate_id
                break

        # 2/3) 标题+年/类型
        if dup_of is None and title_year_key is not None:
            nt, yr, ctype = title_year_key
            for i, okey in enumerate(title_year_keys):
                if okey is None:
                    continue
                ont, oyr, octype = okey
                if octype != ctype:
                    continue
                if ctype == "paper":
                    if oyr == yr:
                        sim = title_similarity(c.title, out[i].title)
                        if sim > paper_title_threshold:
                            dup_of = out[i].candidate_id
                            break
                elif ctype == "dataset":
                    sim = title_similarity(c.title, out[i].title)
                    if sim > dataset_title_threshold:
                        dup_of = out[i].candidate_id
                        break

        if dup_of is not None:
            c.is_duplicate = True
            c.duplicate_of = dup_of
            # 仍记录到 out 用于被后面的 dedup 引用, 但排在后面
            out.append(c)
            seen_fps.append(fp)
            title_year_keys.append(title_year_key)
        else:
            out.append(c)
            seen_fps.append(fp)
            title_year_keys.append(title_year_key)

    return out


def is_duplicate_in_ledger(
    candidate: RetrievalCandidate,
    ledger_items: Iterable,
) -> bool:
    """检查 candidate 是否已存在于 Evidence Ledger.

    ledger_items 是 ``EvidenceItem`` iterable, 检查 DOI / arXiv / repo_full_name / url.
    """

    c_fp = _candidate_fingerprint(candidate)
    if not c_fp:
        return False
    for it in ledger_items:
        fps: set[str] = set()
        if it.doi:
            fps.add(f"_doi_key:{it.doi.strip().lower()}")
        if it.arxiv_id:
            ar = it.arxiv_id.strip().lower()
            for prefix in ("arxiv:", "arXiv:"):
                if ar.startswith(prefix):
                    ar = ar[len(prefix):]
            fps.add(f"_arxiv_key:{ar}")
        if it.url:
            nu = normalize_url(it.url)
            if nu:
                fps.add(f"_url_key:{nu}")
        if hasattr(it, "repository_url") and it.repository_url:
            nu2 = normalize_url(it.repository_url)
            if nu2 and "github.com" in nu2.lower():
                from urllib.parse import urlparse

                u = urlparse(nu2)
                parts = [p for p in u.path.split("/") if p]
                if len(parts) >= 2:
                    fps.add(f"_repo_key:{parts[0].lower()}/{parts[1].lower().rstrip('.git')}")
        if c_fp & fps:
            return True
    return False
