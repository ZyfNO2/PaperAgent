"""Quality filter prompt — judges whether each candidate is a real academic paper.

LLM is the primary path; heuristic regex fallback is used only when LLM is
unavailable. No hardcoded domain blacklist.
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You are an academic paper authenticity auditor. Judge whether each candidate is a real academic paper. Do not use hardcoded keyword lists."""

USER_TEMPLATE = """Candidate papers ({n} total):
{candidates_text}

Judgement criteria:
1. Real academic paper = has research content, authors/institution, publication venue or preprint ID
2. Non-paper = glossary/concept page/directory entry/encyclopedia entry/lecture notes/classification number/figure title/table title
3. Title ending or starting with "Term Entry" / "Core Concept" / "Input Classification" / "Terminology Entry" / "Concept Entry" / "Term Assessment" / "Term List" / "Term Validation" / "Input Evaluation" / "Input Technical Keywords" -> non-paper
4. Title starting with "Figure \\d+" / "Table \\d+:" / "Supplemental Information" -> non-paper
5. Title being a pure generic domain term (e.g. "Deep Learning" / "Large Language Models") without specific research content -> non-paper
6. Abstract being pure definition/pure classification description/pure terminology explanation -> non-paper
7. URL being encyclopedia/dictionary/teaching site -> non-paper

Note: the above rules serve as judgement dimensions, NOT hardcoded filters. Use LLM understanding to comprehensively judge each candidate.

Output JSON array, each element:
{{"index": 0, "is_paper": true, "reason": "has research content and experiments"}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON array — no prose, no fences.
"""


def build_batch(candidates: list[dict[str, Any]]) -> dict[str, str]:
    """Build prompt for a batch of candidates."""
    lines: list[str] = []
    for i, c in enumerate(candidates):
        title = (c.get("title") or c.get("name") or "").strip()
        snippet = (c.get("abstract") or c.get("description") or "")[:200]
        url = c.get("url") or ""
        source = c.get("source") or ""
        lines.append(f"[{i}] Title: {title}\n    Abstract: {snippet}\n    URL: {url}\n    Source: {source}")
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            n=len(candidates),
            candidates_text="\n".join(lines),
        ),
    }
