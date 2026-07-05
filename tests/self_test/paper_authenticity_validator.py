"""Self-test validator: paper authenticity — detects LLM-hallucinated non-paper entries.

Checks verified_papers and weak_papers for known pollution patterns that indicate
the LLM generated fake "paper" entries (e.g. "Term Entry", "Core Concept", "Figure N").
"""
from __future__ import annotations

import re
from typing import Any


POLLUTION_PATTERNS = [
    r"Term\s*Entry",
    r"Core\s*Concept",
    r"Input\s*Classification",
    r"Terminology\s*Entry",
    r"Concept\s*Entry",
    r"Term\s*Assessment",
    r"Term\s*List",
    r"Term\s*Validation",
    r"Input\s*Evaluation",
    r"Input\s*Technical\s*Keywords",
    r"^Figure\s*\d+",
    r"^Table\s*\d+",
    r"Supplemental\s*Information",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in POLLUTION_PATTERNS]


def _is_polluted(title: str) -> bool:
    return any(pat.search(title) for pat in COMPILED_PATTERNS)


def validate(state: dict[str, Any]) -> dict[str, Any]:
    """Validate that no hallucinated non-paper entries leaked into verified/weak papers.

    Returns:
        dict with keys: pass (bool), n_checked, polluted_titles, details
    """
    verified = state.get("verified_papers") or []
    weak = state.get("weak_papers") or []
    expanded = state.get("expanded_papers") or []

    all_papers = []
    for p in verified:
        all_papers.append(("verified", p))
    for p in weak:
        all_papers.append(("weak", p))
    for p in expanded:
        all_papers.append(("expanded", p))

    polluted = []
    for source, p in all_papers:
        title = p.get("title", "")
        if _is_polluted(title):
            polluted.append({"source": source, "title": title})

    passed = len(polluted) == 0

    return {
        "pass": passed,
        "n_checked": len(all_papers),
        "n_polluted": len(polluted),
        "polluted_titles": polluted,
        "details": (
            f"All {len(all_papers)} papers clean (0 pollution)"
            if passed
            else f"{len(polluted)} polluted entries found: {[p['title'] for p in polluted[:5]]}"
        ),
    }
