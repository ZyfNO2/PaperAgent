"""Re6.4 Novelty Review — The reviewer pressure-test adapter.

Implements the 5-dimension reviewer test:
  repetition, motivation, falsifiability, differentiation, story.

Acts as an independent critic against NoveltyCandidate claims, bound to
the contract 'novelty-review/v1'.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

NOVELTY_REVIEW_SYSTEM = (
    "You are an anonymous reviewer evaluating research novelty claims. "
    "Perform a rigorous pressure test across 5 dimensions. "
    "Every criticism MUST cite an evidence_id from the input. "
    "If no evidence exists for a dimension, write 'unknown' as evidence_id. "
    "Output ONLY valid JSON."
)

NOVELTY_REVIEW_PROMPT = """Evaluate the novelty candidate against 5 reviewer dimensions.

Topic: {topic}

Novelty Candidate:
{novelty_json}

Evidence Context (papers, chunks, verified facts):
{evidence_context}

---

For each dimension, provide a reviewer pressure point:

1. **repetition**: Is this approach already published? Does it genuinely differ from prior work?
2. **motivation**: Is the problem gap real and supported by evidence? Or is it motivation by model-availability?
3. **falsifiability**: Can the claims be disproven? What experiment would refute them?
4. **differentiation**: How does each module actually differ from baselines (not just "we added X")?
5. **story**: Does the narrative connect Problem→Method→Insight logically without gaps?

Output JSON:
{{
  "verdict": "accepted" | "weak_reject" | "reject",
  "novelty_score": 0-10,
  "pseudo_innovation_risks": ["risk1", "risk2"],
  "pressure_points": [
    {{
      "risk": "repetition" | "motivation" | "falsifiability" | "differentiation" | "story",
      "question": "reviewer question",
      "severity": "high" | "medium" | "low",
      "repair": "suggested fix",
      "evidence_ids": ["id1", "id2"]
    }}
  ],
  "differentiation_matrix": [
    {{
      "adjacent_work_id": "paper_id",
      "adjacent_work_label": "Paper Title",
      "problem_diff": "...",
      "method_diff": "...",
      "detail_diff": "...",
      "evidence_diff": "...",
      "insight_diff": "..."
    }}
  ],
  "required_repairs": ["repair1", "repair2"],
  "strengths": ["strength1"],
  "risks": ["risk1"]
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


def build_novelty_review_prompt(state: ResearchState) -> str:
    """Build the novelty review prompt from state."""
    topic = state.get("topic", "")
    innovation_points = state.get("innovation_points", [])
    verified_papers = state.get("verified_papers", [])
    baseline_candidates = state.get("baseline_candidates", [])
    parallel_candidates = state.get("parallel_candidates", [])
    binding_validation = state.get("binding_validation", {})

    # Build evidence context
    evidence_parts: list[str] = []
    for paper in verified_papers[:10]:
        evidence_parts.append(
            f"[{paper.get('candidate_id', 'unknown')}] {paper.get('title', '')} "
            f"({paper.get('year', '')}) — {paper.get('abstract', '')[:200]}"
        )
    for paper in (baseline_candidates or [])[:5]:
        evidence_parts.append(
            f"[{paper.get('id', 'unknown')}] {paper.get('title', '')} (baseline)"
        )

    # Serialize novelty candidates
    novelty_json = json.dumps(
        {
            "innovation_points": innovation_points,
            "binding_validation": binding_validation,
        },
        ensure_ascii=False,
        default=str,
    )[:4000]

    return NOVELTY_REVIEW_PROMPT.format(
        topic=topic,
        novelty_json=novelty_json,
        evidence_context="\n".join(evidence_parts) if evidence_parts else "no evidence available",
    )


def parse_novelty_review_output(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse and normalize the reviewer output."""
    return {
        "novelty_review_verdict": raw.get("verdict", "reject"),
        "novelty_review_score": raw.get("novelty_score", 0),
        "pseudo_innovation_risks": raw.get("pseudo_innovation_risks", []),
        "pressure_points": raw.get("pressure_points", []),
        "differentiation_matrix": raw.get("differentiation_matrix", []),
        "required_repairs": raw.get("required_repairs", []),
        "review_strengths": raw.get("strengths", []),
        "review_risks": raw.get("risks", []),
    }
