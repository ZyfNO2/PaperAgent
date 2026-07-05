"""Self-test validator: topic relevance — checks verified papers relate to the topic.

Verifies that ≥30% of verified paper titles contain at least one keyword from
the topic_atoms (method, object, task fields).
"""
from __future__ import annotations

from typing import Any


def _extract_keywords(topic_atoms: dict[str, Any]) -> list[str]:
    """Extract lowercase keywords from topic_atoms."""
    keywords: list[str] = []
    for field in ("method", "object", "task", "domain"):
        val = topic_atoms.get(field, "")
        if isinstance(val, str) and val.strip():
            keywords.append(val.strip().lower())
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str) and v.strip():
                    keywords.append(v.strip().lower())
    return keywords


def _title_matches(title: str, keywords: list[str]) -> bool:
    """Check if title contains any of the keywords (word-level matching)."""
    title_lower = title.lower()
    for kw in keywords:
        if len(kw) < 3:
            continue
        # For multi-word keywords, check if any significant word matches
        words = kw.split()
        for w in words:
            if len(w) >= 4 and w in title_lower:
                return True
        # Also check the full phrase
        if kw in title_lower:
            return True
    return False


def validate(state: dict[str, Any]) -> dict[str, Any]:
    """Validate that verified papers are topically relevant.

    Returns:
        dict with keys: pass (bool), n_verified, n_relevant, relevance_rate, details
    """
    verified = state.get("verified_papers") or []
    topic_atoms = state.get("topic_atoms") or {}

    keywords = _extract_keywords(topic_atoms)

    if not verified:
        return {
            "pass": False,
            "n_verified": 0,
            "n_relevant": 0,
            "relevance_rate": 0.0,
            "details": "No verified papers to check",
        }

    if not keywords:
        # Fallback: use topic string itself
        topic = state.get("topic", "")
        if topic:
            keywords = [w.lower() for w in topic.split() if len(w) >= 3]

    n_relevant = 0
    for p in verified:
        title = p.get("title", "")
        if _title_matches(title, keywords):
            n_relevant += 1

    rate = n_relevant / len(verified) if verified else 0.0
    passed = rate >= 0.30

    return {
        "pass": passed,
        "n_verified": len(verified),
        "n_relevant": n_relevant,
        "relevance_rate": round(rate, 3),
        "keywords_used": keywords[:10],
        "details": (
            f"{n_relevant}/{len(verified)} papers relevant ({rate:.0%})"
            if verified
            else "No verified papers"
        ),
    }
