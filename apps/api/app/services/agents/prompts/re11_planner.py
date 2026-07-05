"""Search planner prompt (Re1.2 Agent A2).

Outputs search_plan:
{
  "queries": [
    {"tool": "arxiv|openalex|crossref|web|github",
     "query": str, "why": str,
     "expected_evidence": str, "stop_condition": str},
    ...
  ],
  "rounds": ["broad", "focused", "repair"],   # at least "broad" included
  "negative_feedback": str,
}

Two planner modes:
 - initial  -> no prior_rounds
 - followup -> inject prior rejection reasons into `why` + negative_feedback
"""
from __future__ import annotations

import json
from typing import Any


SYSTEM = """You are a research search planner. Given a concrete academic topic and
its parsed atoms, design a short multi-tool search plan.

Available tools:
- arxiv:         CS/AI/engineering papers; latest preprints
- openalex:      academic papers / reviews by method/object/task
- crossref:      DOI / journal papers (use when arxiv is thin)
- web:           metadata gaps — dataset pages, project pages, benchmarks
- github:        official code repos — ONLY when a known method or paper title exists

RULES:
1. Every query MUST specify exactly one tool.
2. Every query MUST include: tool, query, why, expected_evidence, stop_condition.
3. `stop_condition` is a concrete stopping rule, e.g. "stop after 5 consecutive
   results with hit_keywords >= 2 and relation_to_topic == direct".
4. Prefer picking dataset/repo from verified papers (Re1.1 §9); do NOT search
   github for generic method names.
5. Broad round MUST be present; focused/repair only when justified by gaps.
6. Return a single JSON object — no prose, no fences.
"""

_INITIAL_TEMPLATE = """Topic: {topic}
Atoms:
{atoms_json}

Produce an initial search plan (broad round).
Return JSON with EXACTLY these top-level keys:
- "queries": list of query objects (tool/query/why/expected_evidence/stop_condition)
- "rounds":        list of round kinds (ALWAYS include "broad")
- "negative_feedback": ""   (empty string on the initial plan)
"""

_FOLLOWUP_TEMPLATE = """Topic: {topic}
Atoms:
{atoms_json}

Completed prior rounds (each with tool_executions + accept/reject summary):
{prior_json}

Produce the NEXT search plan that FIXES only the gaps revealed by the prior
rounds. DO NOT repeat queries that already succeeded; rotate to new tools or
keywords when a tool was exhausted (stop_condition met).

Return JSON with EXACTLY these top-level keys:
- "queries": list of query objects (tool/query/why/expected_evidence/stop_condition)
- "rounds":        list of round kinds (e.g. ["focused"] or ["repair"])
- "negative_feedback": concise summary of the prior-round failure causes + how
                       this round avoids them
"""


def build(
    topic: str,
    atoms: dict[str, Any],
    *,
    prior_rounds: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    atoms_json = json.dumps(atoms or {}, ensure_ascii=False, indent=2)
    if not prior_rounds:
        user = _INITIAL_TEMPLATE.format(topic=topic, atoms_json=atoms_json)
    else:
        prior_json = json.dumps(prior_rounds, ensure_ascii=False, indent=2)
        user = _FOLLOWUP_TEMPLATE.format(
            topic=topic, atoms_json=atoms_json, prior_json=prior_json,
        )
    return {"system": SYSTEM, "user": user}
