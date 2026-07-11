"""Re7.6 Claim Judge — D-12.

Final gate before novelty claims enter the report. Enforces:
  - P-M-I completeness with evidence binding
  - First claim downgrade
  - Adjacent work differentiation
  - Falsifiable support/refute/test requirements
  - Stale evidence detection
"""
from __future__ import annotations

import logging
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

CLAIM_JUDGE_SYSTEM = (
    "You are a research integrity judge. Evaluate novelty claims against "
    "strict evidence and methodological standards. Reject claims that "
    "are not backed by verifiable evidence. Output ONLY valid JSON."
)

CLAIM_JUDGE_PROMPT = """Evaluate each novelty claim candidate against the P-M-I framework.

Topic: {topic}

Candidates to judge:
{novelty_json}

Evidence Index:
{evidence_text}

For each candidate, judge:
1. **Problem**: Is the gap specific, bounded, and evidence-backed? (not generic "X is important")
2. **Method**: Is the intervention directly targeting the gap? (not engineering stack)
3. **Insight**: Is there a conditional finding beyond metric improvement? (not "F1 improved 5%")
4. **Differentiation**: Does it differ from adjacent work in 5 dimensions?
5. **Evidence binding**: Does each claim have problem/method/insight evidence_ids?
6. **First claim**: If first, is it downgraded to needs_literature_verification?
7. **Falsifiability**: Are support/refute conditions and required test defined?

Output JSON:
{{
  "judgements": [
    {{
      "candidate_id": "id",
      "pmi_valid": true,
      "evidence_complete": true,
      "differentiation_valid": true,
      "first_claim_correctly_downgraded": true,
      "falsifiability_defined": true,
      "verdict": "ACCEPT" | "REVISE" | "REJECT",
      "issues": ["issue1"],
      "required_fixes": ["fix1"]
    }}
  ],
  "overall_verdict": "ACCEPT" | "REVISE" | "REJECT",
  "blocked_items": ["candidate_id or issue"],
  "summary": "overall assessment"
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object."""


def build_claim_judge_prompt(state: ResearchState) -> str:
    topic = state.get("topic", "")
    novelty_json = str(state.get("innovation_points", []))[:3000]
    evidence = state.get("evidence_contexts", []) or []

    evidence_lines = []
    for i, ctx in enumerate(evidence[:15]):
        if isinstance(ctx, dict):
            evidence_lines.append(
                f"[e{i}] {ctx.get('role','?')}: {ctx.get('snippet','')[:150]}"
            )

    return CLAIM_JUDGE_PROMPT.format(
        topic=topic,
        novelty_json=novelty_json,
        evidence_text="\n".join(evidence_lines) if evidence_lines else "no evidence",
    )


def parse_claim_judge_output(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_judgements": raw.get("judgements", []),
        "claim_judge_verdict": raw.get("overall_verdict", "REVISE"),
        "blocked_items": raw.get("blocked_items", []),
        "claim_judge_summary": raw.get("summary", ""),
    }


def claim_judge_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: judge novelty claims against P-M-I standards."""
    innovation_points = state.get("innovation_points", [])

    if not innovation_points:
        return {
            "claim_judgements": [],
            "claim_judge_verdict": "REJECT",
            "blocked_items": [],
            "claim_judge_summary": "no innovation points to judge",
        }

    prompt = build_claim_judge_prompt(state)

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system=CLAIM_JUDGE_SYSTEM,
            node_name="claim_judge",
            profile="premium_review",
            contract_id="claim-judge/v1",
            max_tokens=2000,
            timeout=45.0,
            fallback={
                "judgements": [],
                "overall_verdict": "REJECT",
                "blocked_items": [],
                "summary": "judge unavailable",
            },
        )
        result = parse_claim_judge_output(raw)
        logger.info("claim_judge: verdict=%s judgements=%d",
                     result["claim_judge_verdict"],
                     len(result["claim_judgements"]))
        return result
    except Exception as exc:
        logger.warning("claim_judge: LLM call failed: %s", exc)
        return {
            "claim_judgements": [],
            "claim_judge_verdict": "REJECT",
            "blocked_items": [],
            "claim_judge_summary": f"judge unavailable: {exc}",
        }
