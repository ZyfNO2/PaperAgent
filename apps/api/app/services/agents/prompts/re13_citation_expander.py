"""Citation expander prompt — identify survey papers from expanded citations."""
from __future__ import annotations

from typing import Any

SYSTEM = """You are a literature analysis expert. Identify survey papers from expanded citations."""

USER_TEMPLATE = """Expanded papers ({n} total):
{papers_text}

Identification criteria:
1. Survey = title contains survey/review/tutorial/systematic/benchmark AND content is a domain summary
2. Research paper = has clear method contribution and experiments
3. Uncertain -> mark needs_review

Output JSON array:
{{"index": 0, "is_survey": false, "title": "...", "reason": "..."}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON array — no prose, no fences.
"""


def build_survey_check(papers: list[dict[str, Any]]) -> dict[str, str]:
    """Build prompt for survey identification of expanded papers."""
    lines: list[str] = []
    for i, p in enumerate(papers):
        title = (p.get("title") or "").strip()
        venue = p.get("venue") or ""
        lines.append(f"[{i}] Title: {title}\n    Venue: {venue}")
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            n=len(papers),
            papers_text="\n".join(lines),
        ),
    }
