"""Session 61 M4: RepoCandidateEnhancer.

Heuristic-only GitHub candidate enhancement. No LLM, no network. Adds
stars / updated_at / language / license / training-script hint / warnings.

Ponytail: ranker sorts; this module only annotates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from ...schemas_retrieval import RetrievalCandidate


RepoWarning = Literal[
    "stale_repo",
    "no_license",
    "low_star",
    "unclear_training_script",
    "needs_manual_check",
]


@dataclass
class RepoEnhancementResult:
    stars: int | None = None
    updated_at: str | None = None
    language: str | None = None
    license: str | None = None
    has_training_script_hint: bool = False
    warnings: list[RepoWarning] = field(default_factory=list)


_TRAINING_KEYWORDS = ("train.py", "training", "has_train", "train", "training_script")
_STALE_DAYS = 365 * 2  # 2 years


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # 容忍 Z 后缀
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def enhance_repo(candidate: RetrievalCandidate) -> RepoEnhancementResult:
    c = candidate
    raw = c.raw or {}

    lic = (c.license or "").strip() or None
    stars = c.stars
    updated_at = c.updated_at
    language = raw.get("language")

    description = (raw.get("description") or "")
    topics = [str(t).lower() for t in raw.get("topics", []) or []]
    readme_present = bool(raw.get("has_readme")) or bool(raw.get("readme"))

    desc_topics = (description + " " + " ".join(topics)).lower()
    has_training_script_hint = any(kw.lower() in desc_topics for kw in _TRAINING_KEYWORDS)

    warnings: list[RepoWarning] = []

    if not lic:
        warnings.append("no_license")

    if stars is not None and stars < 10:
        warnings.append("low_star")

    dt = _parse_iso(updated_at)
    if dt is not None:
        now = datetime.now(timezone.utc)
        if (now - dt).days > _STALE_DAYS:
            warnings.append("stale_repo")
    elif updated_at is None:
        # 没更新时间 -> 算 stale
        warnings.append("stale_repo")

    if not has_training_script_hint:
        warnings.append("unclear_training_script")

    if not description and not readme_present:
        warnings.append("needs_manual_check")

    return RepoEnhancementResult(
        stars=stars,
        updated_at=updated_at,
        language=language,
        license=lic,
        has_training_script_hint=has_training_script_hint,
        warnings=warnings,
    )


if __name__ == "__main__":
    # ponytail: self-check
    base = dict(
        candidate_id="r1",
        project_id="p1",
        candidate_type="repo",
        source="github",
        title="3d damage detection",
    )

    # 1) stars=2, no license, no description -> all 4 warnings
    r1 = enhance_repo(RetrievalCandidate(**base, stars=2))
    for w in ("no_license", "low_star", "unclear_training_script", "needs_manual_check"):
        assert w in r1.warnings, (w, r1.warnings)

    # 2) stars=500, MIT, recent, has training keywords -> clean (readme 缺失可能仍 warning)
    r2 = enhance_repo(RetrievalCandidate(
        **base,
        stars=500,
        license="MIT",
        updated_at="2025-01-01T00:00:00Z",
        raw={"description": "pytorch training script for 3d damage detection", "has_readme": True},
    ))
    for w in ("no_license", "low_star", "unclear_training_script", "stale_repo", "needs_manual_check"):
        assert w not in r2.warnings, (w, r2.warnings)
    assert r2.has_training_script_hint is True

    print("OK repo_enhancer self-check passed")