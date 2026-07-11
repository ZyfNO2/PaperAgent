"""Re6.4 Falsifiability Planner — converts Insights into falsifiable propositions."""
from __future__ import annotations

import json
import logging
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

FALSIFIABILITY_SYSTEM = (
    "You are a scientific methodologist. Convert accepted insights into "
    "falsifiable propositions. Each proposition MUST be testable. "
    "If you cannot design a test, mark it as planned_not_verified. "
    "Never present a planned test as verified. Output ONLY valid JSON."
)

FALSIFIABILITY_PROMPT = """Convert each accepted insight into 1-3 falsifiable propositions.

Topic: {topic}

Innovation Points:
{innovation_json}

For each insight that has status=accepted or status=verified, create propositions:

Output JSON:
{{
  "propositions": [
    {{
      "proposition_id": "fp-001",
      "proposition": "The precise mechanistic claim",
      "scoped_setting": "applicable data/task conditions",
      "observable_effect": "what measurable difference we expect",
      "support_condition": "what result would support the claim",
      "refute_condition": "what result would refute the claim",
      "required_test": "specific experiment to run",
      "evidence_ids": ["id1"],
      "status": "planned_not_verified"
    }}
  ]
}}

Rules:
- If a required_test cannot be executed with available resources → status=planned_not_verified
- If evidence supports the claim → status=verified
- If evidence contradicts → status=refuted
- Default to planned_not_verified unless proven otherwise

[OUTPUT CONTRACT] Reply ONLY with the JSON object."""


def build_falsifiability_prompt(state: ResearchState) -> str:
    topic = state.get("topic", "")
    innovation_points = state.get("innovation_points", [])
    binding_validation = state.get("binding_validation", {})

    accepted = [
        ip for ip in innovation_points
        if isinstance(ip, dict) and ip.get("status") in ("accepted", "verified")
    ]

    if not accepted:
        innovation_json = json.dumps(innovation_points[:5], ensure_ascii=False, default=str)
    else:
        innovation_json = json.dumps(accepted, ensure_ascii=False, default=str)

    return FALSIFIABILITY_PROMPT.format(
        topic=topic,
        innovation_json=innovation_json[:4000],
    )


def parse_falsifiability_output(raw: dict[str, Any]) -> dict[str, Any]:
    propositions = raw.get("propositions", [])
    for p in propositions:
        if p.get("status") == "verified" and not p.get("evidence_ids"):
            p["status"] = "planned_not_verified"

    return {"falsifiable_propositions": propositions}


def falsifiability_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: generate falsifiable propositions from innovation points.

    Only generates propositions for accepted/verified innovation points.
    If no innovation points, returns empty list.
    """
    innovation_points = state.get("innovation_points", [])

    if not innovation_points:
        return {"falsifiable_propositions": []}

    has_accepted = any(
        isinstance(ip, dict) and ip.get("status") in ("accepted", "verified")
        for ip in innovation_points
    )
    if not has_accepted:
        return {"falsifiable_propositions": []}

    prompt = build_falsifiability_prompt(state)

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system=FALSIFIABILITY_SYSTEM,
            node_name="falsifiability",
            profile="premium_review",
            contract_id="falsifiability-batch/v1",
            max_tokens=2000,
            timeout=45.0,
            fallback={"propositions": []},
        )
        result = parse_falsifiability_output(raw)
        logger.info("falsifiability: generated %d propositions",
                     len(result.get("falsifiable_propositions", [])))
        return result
    except Exception as exc:
        logger.warning("falsifiability: LLM call failed: %s", exc)
        return {"falsifiable_propositions": []}
