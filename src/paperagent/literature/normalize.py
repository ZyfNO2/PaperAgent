from __future__ import annotations

import re
from hashlib import sha256

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "http://dx.doi.org/",
    "https://dx.doi.org/",
    "doi:",
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ARXIV_VERSION = re.compile(r"v\d+$", re.IGNORECASE)


def canonical_doi(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for prefix in _DOI_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = normalized.strip()
    return normalized or None


def canonical_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/", "arxiv:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = _ARXIV_VERSION.sub("", normalized).strip()
    return normalized or None


def normalized_text(value: str) -> str:
    return _NON_ALNUM.sub(" ", value.lower()).strip()


def normalized_author(value: str | None) -> str:
    return normalized_text(value or "")


def stable_paper_id(
    *,
    doi: str | None,
    arxiv_id: str | None,
    title: str,
    year: int | None,
    first_author: str,
) -> str:
    if doi:
        key = f"doi:{doi}"
    elif arxiv_id:
        key = f"arxiv:{arxiv_id}"
    else:
        key = f"title:{normalized_text(title)}|year:{year}|author:{normalized_author(first_author)}"
    return "paper-" + sha256(key.encode("utf-8")).hexdigest()[:20]
