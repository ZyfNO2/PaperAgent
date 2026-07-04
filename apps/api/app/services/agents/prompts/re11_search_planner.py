"""Search planner prompt (Re1.1 §8.1).

Outputs search_rounds + tool_calls, where every tool call includes:
  tool_name / query / why_call / expected_evidence_type / stop_condition
and a negative_feedback section describing prior-round failures.
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You are a search planner. For each round, propose specific tool calls.
Every tool call MUST include: tool_name, query, why_call, expected_evidence_type,
stop_condition. Do not combine multiple tool ideas into one call.

Available tools:
- search_openalex: academic papers/reviews by method/object/task
- search_arxiv: CS/AI/engineering papers, recent
- search_crossref: DOI / journal papers when arxiv is thin
- search_github: official implementation — ONLY with a known method or paper title
- web_search: metadata gaps (dataset pages, project pages)

Priority for dataset/repo (Re1.1 §9): prefer picking from verified papers,
then title-reverse lookup, then dataset-name reverse lookup, then lastly
topic-level broad search. Fix: do NOT search GitHub with generic method names."""

USER_TEMPLATE = """Topic: {topic}
Atoms: {atoms}
Round: {round_ix} of {max_rounds} ({round_kind})
Prior errors / negative feedback: {negative_feedback}

Return JSON:
- search_rounds: list of rounds, each with:
    - round_ix, kind ("broad"|"focused"|"seed_expansion"|"repair")
    - tool_calls: list of {tool_name, query, why_call,
        expected_evidence_type, stop_condition}
- negative_feedback: string summarizing prior-round failure causes + how
  this round avoids them. Empty string if round 0."""

USER_ROUND_TEMPLATE = """Topic: {topic}
Atoms: {atoms}
Completed prior rounds (candidates accepted / rejected): {prior_summary}

Plan the next round as JSON:
- tool_calls (each with tool_name, query, why_call,
  expected_evidence_type, stop_condition)
- negative_feedback: what failed previously + how this round fixes it"""


def build(
    topic: str,
    atoms: dict[str, Any],
    *,
    round_ix: int,
    max_rounds: int,
    round_kind: str,
    negative_feedback: str = "",
) -> dict[str, str]:
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            topic=topic,
            atoms=atoms,
            round_ix=round_ix,
            max_rounds=max_rounds,
            round_kind=round_kind,
            negative_feedback=negative_feedback,
        ),
    }


def build_from_prior(
    topic: str,
    atoms: dict[str, Any],
    prior_summary: str,
) -> dict[str, str]:
    return {
        "system": SYSTEM,
        "user": USER_ROUND_TEMPLATE.format(
            topic=topic,
            atoms=atoms,
            prior_summary=prior_summary,
        ),
    }
