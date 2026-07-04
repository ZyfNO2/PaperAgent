"""Dataset / repo extractor from verified papers (Re1.1 §8.2 / §9).

For each verified paper, extract:
  dataset_name / benchmark_name / official_code_url / project_page_url /
  supplementary_url / paper_mentioned_repo / paper_used_baseline

If the paper gives no dataset/repo, output not_found_in_paper (do NOT fabricate).
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You extract dataset and code links that the PAPER itself mentions.
If the paper does not provide a dataset or repo, output not_found_in_paper.
Do NOT fabricate URLs because the topic suggests COCO/ORB-SLAM/etc. — that is a
hallucination. If missing, mark url_missing_needs_repair rather than failing."""

USER_TEMPLATE = """Paper: {title}
Abstract: {abstract}
Snippet (fulltext / supplementary, if any): {snippet}

Return JSON:
- dataset_name: str | null
- benchmark_name: str | null
- official_code_url: str | null
- project_page_url: str | null
- supplementary_url: str | null
- paper_mentioned_repo: str | null
- paper_used_baseline: list[str]
- missing: list[str] — evidence gaps ("dataset", "code_url", "project_url")
- status: "found" | "not_found_in_paper" | "url_missing_needs_repair\""""


def build(title: str, abstract: str = "", snippet: str = "") -> dict[str, str]:
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            title=title,
            abstract=(abstract or "")[:800],
            snippet=(snippet or "")[:600],
        ),
    }
