"""Targeted repair prompt (Re1.2 Agent A3).

Used by targeted_repair_node to re-plan ONLY the failing evidence slice. The
output schema is intentionally identical to the search planner output so the
same patch shape can overwrite state["search_plan"]:

  {
    "queries": [...each with tool/query/why/expected_evidence/stop_condition]...,
    "rounds": ["repair"],
    "negative_feedback": str,
  }

The prompt cites SPECIFIC gaps (numbers + titles + failure reasons) so the LLM
targets a concrete repair_type instead of proposing another broad sweep.
"""
from __future__ import annotations

import json
from typing import Any


SYSTEM = """You are a targeted research-gap repair planner. The last broad/focused
search round came back short on one evidence slice. Re-plan ONLY that slice.

Available tools:
- arxiv:    academic papers (use for paper_gap and baseline_gap)
- openalex: academic papers / reviews; good for dataset / baseline gaps
- crossref: DOI / journal papers; use for target paper you have DOI/title for
- web:      dataset pages / project pages / benchmarks (url_repair +
            metadata_mismatch_repair)
- github:   official repos (repo_gap_repair); ONLY when you can name a paper or
           method to disambiguate

Re3.0 Strategy switching (choose one):
- "synonym": Replace keywords with synonyms or related terms
    (e.g. "YOLO crop" → "object detection agriculture" → "plant disease detection")
- "broaden": Remove qualifiers and search more broadly
    (e.g. "YOLO crop recognition" → "YOLO" or "crop detection")
- "switch_tool": If a specific adapter returned 0 results, try a different tool
    for the same query (e.g. OpenAlex 429 → use Crossref or arxiv)

Hard rules:
1. Output a SINGLE JSON object with EXACTLY these top-level keys:
     "queries", "rounds", "negative_feedback", "strategy".
2. "rounds" MUST be ["repair"] (this is a repair round, not a broad sweep).
3. "strategy" MUST be one of: "synonym", "broaden", "switch_tool".
4. Every query MUST include: tool, query, why, expected_evidence, stop_condition.
5. `why` MUST explicitly name the prior failed query it replaces and the
   gap-closing strategy.
6. `stop_condition` MUST be stricter than the failing query's condition so
   we fail fast if the gap truly does not exist.
7. NEVER repeat any query from `prior_queries` (case-insensitive match). The
   LLM must rotate tools, keywords, or language.
8. NO prose outside the JSON object.
"""


def build(
    topic: str,
    gaps: dict[str, Any],
    rejected_titles: list[str],
    prior_queries: list[str],
) -> dict[str, Any]:
    return {
        "system": SYSTEM,
        "user": (
            f"Topic: {topic}\n\n"
            "Quantitative gaps in current evidence:\n"
            f"{json.dumps(gaps, ensure_ascii=False, indent=2)}\n\n"
            "Titles / candidates that were REJECTED in the last round "
            "(unrelated / weak / off-topic):\n"
            f"{json.dumps(rejected_titles, ensure_ascii=False, indent=2)}\n\n"
            "Queries that were ALREADY TRIED in earlier rounds — DO NOT "
            "repeat any of these (case-insensitive):\n"
            f"{json.dumps(prior_queries, ensure_ascii=False, indent=2)}\n\n"
            "Return a JSON object:\n"
            '  {"queries": [ {tool, query, why, expected_evidence, stop_condition}, ... ],'
            '   "rounds": ["repair"],'
            '   "negative_feedback": "<why the prior round failed + how this closes the gap>",'
            '   "strategy": "synonym|broaden|switch_tool"}'
        ),
    }
