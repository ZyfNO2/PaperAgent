"""候选评分 (SOP §11)."""

from __future__ import annotations

import re
from datetime import datetime

from ...schemas_retrieval import RetrievalCandidate


def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _contains(text: str | None, needles: list[str]) -> float:
    if not text or not needles:
        return 0.0
    t = text.lower()
    hits = 0
    for n in needles:
        if n and n.lower() in t:
            hits += 1
    return _clip01(hits / max(1, len(needles)))


def _recency_score(year: int | None) -> float:
    if year is None:
        return 0.3
    now_year = datetime.utcnow().year
    age = max(0, now_year - year)
    if age <= 1:
        return 1.0
    if age <= 3:
        return 0.85
    if age <= 5:
        return 0.65
    if age <= 8:
        return 0.45
    return 0.25


def _citation_signal(citation_count: int | None) -> float:
    if not citation_count:
        return 0.3
    if citation_count >= 200:
        return 1.0
    if citation_count >= 50:
        return 0.85
    if citation_count >= 10:
        return 0.6
    if citation_count >= 1:
        return 0.4
    return 0.2


def _stars_normalized(stars: int | None) -> float:
    if not stars:
        return 0.0
    if stars >= 5000:
        return 1.0
    if stars >= 1000:
        return 0.9
    if stars >= 300:
        return 0.75
    if stars >= 100:
        return 0.6
    if stars >= 30:
        return 0.45
    if stars >= 10:
        return 0.3
    return 0.15


def _accessibility_hint(c: RetrievalCandidate) -> float:
    s = 0.5
    if c.url:
        s += 0.2
    if c.license:
        s += 0.2
    if c.year is not None and c.year >= 2018:
        s += 0.1
    return _clip01(s)


def _license_hint(c: RetrievalCandidate) -> float:
    if not c.license:
        return 0.2
    lic = c.license.lower()
    if any(k in lic for k in ("mit", "apache", "bsd", "cc-by", "cc0", "public domain")):
        return 1.0
    if any(k in lic for k in ("gpl", "lgpl", "agpl")):
        return 0.7
    if "unknown" in lic or "other" in lic:
        return 0.3
    return 0.5


def _usage_signal(c: RetrievalCandidate) -> float:
    s = 0.0
    if c.citation_count:
        s += min(1.0, c.citation_count / 100.0) * 0.6
    if c.stars:
        s += _stars_normalized(c.stars) * 0.4
    return _clip01(s)


def _source_reliability(c: RetrievalCandidate) -> float:
    return {
        "openalex": 0.9,
        "arxiv": 0.85,
        "semantic_scholar": 0.85,
        "github": 0.8,
        "huggingface": 0.7,
        "kaggle": 0.65,
        "manual_fallback": 0.3,
    }.get(c.source, 0.4)


def _recent_activity(updated_at: str | None) -> float:
    if not updated_at:
        return 0.3
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", updated_at)
    if not m:
        return 0.3
    try:
        y = int(m.group(1))
    except ValueError:
        return 0.3
    return _recency_score(y)


def _language_match(c: RetrievalCandidate) -> float:
    raw = c.raw or {}
    lang = (raw.get("language") or "").lower()
    if lang in ("python", "pytorch", "tensorflow", "jupyter notebook"):
        return 0.9
    if lang in ("c++", "c", "rust", "go", "java", "javascript", "typescript"):
        return 0.6
    if not lang:
        return 0.4
    return 0.5


def _framework_hint(c: RetrievalCandidate) -> float:
    text = ((c.abstract or "") + " " + (c.title or "")).lower()
    if any(k in text for k in ("pytorch", "torch", "tensorflow", "keras", "huggingface", "transformers")):
        return 0.9
    if any(k in text for k in ("sklearn", "scikit-learn", "xgboost", "lightgbm")):
        return 0.7
    return 0.4


def _readme_hint(c: RetrievalCandidate) -> float:
    raw = c.raw or {}
    if raw.get("has_readme") or raw.get("description"):
        return 0.85
    return 0.3


def score_paper(c: RetrievalCandidate, *, query_keywords: list[str] | None = None) -> float:
    """SOP §11.1: Paper retrieval score (0..1)."""

    kws = query_keywords or c.matched_keywords or []
    title_match = _contains(c.title, kws)
    abstract_match = _contains(c.abstract, kws)
    task_match = _contains(" ".join([c.title or "", c.abstract or "", c.venue or ""]), kws)
    object_match = _contains(c.title, kws)
    method_match = _contains(c.abstract, kws)
    recency = _recency_score(c.year)
    citation = _citation_signal(c.citation_count)

    score = (
        0.25 * title_match
        + 0.20 * abstract_match
        + 0.15 * task_match
        + 0.15 * object_match
        + 0.10 * method_match
        + 0.10 * recency
        + 0.05 * citation
    )
    return round(_clip01(score), 4)


def score_dataset(c: RetrievalCandidate, *, query_keywords: list[str] | None = None) -> float:
    """SOP §11.2."""

    kws = query_keywords or c.matched_keywords or []
    object_match = _contains(c.title, kws)
    task_match = _contains(" ".join([c.title or "", c.abstract or ""]), kws)
    access = _accessibility_hint(c)
    lic = _license_hint(c)
    usage = _usage_signal(c)
    recency = _recency_score(c.year)
    src = _source_reliability(c)

    score = (
        0.25 * object_match
        + 0.20 * task_match
        + 0.15 * access
        + 0.15 * lic
        + 0.10 * usage
        + 0.10 * recency
        + 0.05 * src
    )
    return round(_clip01(score), 4)


def score_repo(c: RetrievalCandidate, *, query_keywords: list[str] | None = None) -> float:
    """SOP §11.3."""

    kws = query_keywords or c.matched_keywords or []
    task_match = _contains(" ".join([c.title or "", c.abstract or ""]), kws)
    method_match = _contains(c.abstract, kws)
    readme = _readme_hint(c)
    lic = _license_hint(c)
    stars = _stars_normalized(c.stars)
    recent = _recent_activity(c.updated_at)
    lang = _language_match(c)
    framework = _framework_hint(c)

    score = (
        0.20 * task_match
        + 0.15 * method_match
        + 0.15 * readme
        + 0.10 * lic
        + 0.10 * stars
        + 0.10 * recent
        + 0.10 * lang
        + 0.10 * framework
    )
    return round(_clip01(score), 4)
