"""Session 61 M3: DatasetCandidateEnhancer.

Heuristic-only dataset enhancement. No LLM, no network. Adds license / download
availability / benchmark-hint / task-match-score / warnings to a
``RetrievalCandidate``.

Ponytail: explicit rules, no fabrication. Only ``raw["benchmark"] = True`` or
``"benchmark" in raw["tags"]`` may set ``is_benchmark_hint``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ...schemas_retrieval import RetrievalCandidate


DatasetWarning = Literal[
    "license_unknown",
    "low_relevance",
    "not_public",
    "needs_manual_check",
]


@dataclass
class DatasetEnhancementResult:
    license: str | None = None
    has_download: bool = False
    is_benchmark_hint: bool = False
    task_match_score: float = 0.0
    warnings: list[DatasetWarning] = field(default_factory=list)


_UNKNOWN_LICENSE = {"unknown", "other", "", "none", "null"}


def _title_has_keyword(title: str, keywords: list[str]) -> bool:
    title_l = (title or "").lower()
    return any((kw or "").lower() in title_l for kw in keywords if kw)


def enhance_dataset(candidate: RetrievalCandidate) -> DatasetEnhancementResult:
    c = candidate
    raw = c.raw or {}

    lic = (c.license or "").strip()
    lic_l = lic.lower()
    license_unknown = not lic or lic_l in _UNKNOWN_LICENSE

    url = (c.url or "").strip()
    download_raw = raw.get("download") or raw.get("download_url") or ""
    has_download = bool(url) or bool(download_raw)

    is_benchmark_hint = bool(raw.get("benchmark")) or "benchmark" in [
        str(t).lower() for t in raw.get("tags", []) or []
    ]

    title_l = (c.title or "").lower()
    kws = c.matched_keywords or []
    title_match = _title_has_keyword(c.title, kws)
    # 粗略 task match score: title + abstract 中命中 keyword 比例
    haystack = " ".join([c.title or "", c.abstract or ""]).lower()
    if kws:
        hits = sum(1 for kw in kws if (kw or "").lower() in haystack)
        task_match_score = round(hits / max(len(kws), 1), 3)
    else:
        task_match_score = 0.0

    warnings: list[DatasetWarning] = []
    if license_unknown:
        warnings.append("license_unknown")

    if not has_download:
        warnings.append("not_public")

    if not title_match and task_match_score < 0.2:
        warnings.append("low_relevance")

    if c.year is None and (license_unknown or not has_download):
        warnings.append("needs_manual_check")

    return DatasetEnhancementResult(
        license=lic or None,
        has_download=has_download,
        is_benchmark_hint=is_benchmark_hint,
        task_match_score=task_match_score,
        warnings=warnings,
    )


if __name__ == "__main__":
    # ponytail: self-check
    base_kwargs = dict(
        candidate_id="c1",
        project_id="p1",
        candidate_type="dataset",
        source="huggingface",
        title="Concrete Crack Detection Dataset",
        matched_keywords=["crack", "detection"],
    )

    # 1) no license -> license_unknown
    r1 = enhance_dataset(RetrievalCandidate(**base_kwargs))
    assert "license_unknown" in r1.warnings, r1.warnings

    # 2) no url AND no raw.download -> not_public
    r2 = enhance_dataset(RetrievalCandidate(
        **base_kwargs,
        url=None,
        license="MIT",
        raw={},
    ))
    assert "not_public" in r2.warnings, r2.warnings
    assert "license_unknown" not in r2.warnings

    # 3) matching title + license + url + year -> no relevance/license/public warnings
    r3 = enhance_dataset(RetrievalCandidate(
        **base_kwargs,
        url="https://huggingface.co/datasets/x",
        license="MIT",
        year=2024,
    ))
    for w in ("license_unknown", "not_public", "low_relevance"):
        assert w not in r3.warnings, (w, r3.warnings)

    print("OK dataset_enhancer self-check passed")