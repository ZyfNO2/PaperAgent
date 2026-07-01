"""Re02 plan_tools prompt — multi-round, role-aware (SOP §4).

Replaces the Re01 single-shot plan that only emitted arxiv/openalex/
crossref/github query lists. Re02's plan is structured as ROUNDS, each
round a sequence of CALLS, each call carries:

    tool            — search_arxiv | search_openalex | search_crossref | search_github
    query           — noun-phrase, ASCII only, ≤ 6 words (≤ 4 for github)
    target_role     — baseline_or_parallel_paper | survey | repo |
                      dataset | reference | broad_recall | ...
    why_call        — one-sentence justification
    expected_output — paper | repo | dataset
    fallback_tool   — optional adapter to try if primary fails (rate-limit)

Round semantics:
    1 broad_recall           — wide initial sweep
    2 reference_expansion    — paper title follow-up + repo description mine
    3 repo_dataset_followup  — github / dataset-specific pass

This mirrors ARC `_expand_search_queries()` + `_build_default_search_queries()`
broad/tail/survey/benchmark variants, but each variant becomes an explicit
round with a why.
"""

PLAN_TOOLS_SYSTEM = """You are the search planner for an autonomous literature-survey
agent. Given the parsed topic and the user's intent, produce a STRICT JSON
call plan that the runner will fan-out to 4 retrieval adapters ACROSS
MULTIPLE ROUNDS.

===================== NON-NEGOTIABLE RULES =====================
1. Output JSON only. No prose, no markdown, no trailing commentary.
2. The plan has 3 rounds; each round is a list of calls. Each call MUST
   include `tool / query / target_role / why_call / expected_output`.
3. Query length rules per adapter:
   - arxiv / openalex / crossref: ≤ 6 words each
   - github: STRICTLY ≤ 4 words (GitHub search down-ranks long phrases)
4. DO NOT inject author names, paper titles, or repo names. Noun-phrases only.
5. For github queries, AVOID abstract terms like "monitoring system".
   A github search succeeds on concrete method or object words.
6. Round 1 (broad_recall) MUST have ≥ 1 arxiv call. The spine of retrieval.
7. Round 2 (reference_expansion) MUST include paper-title follow-ups —
   emit a small list of generic expansion queries that will surface
   adjacent papers, e.g. "<method> benchmark", "<method> recent advances",
   "<object> survey". LITERAL paper titles are forbidden; noun-phrases only.
8. Round 3 (repo_dataset_followup) MUST include ≥ 1 github call whose
   target_role is "repo" or "dataset".
9. `top_k_per_adapter` ≤ 8. `year_min` ≥ 2018.
10. Tools may be referenced by either `search_arxiv` / `search_openalex` /
    `search_crossref` / `search_github` (new names) OR the legacy
    `arxiv / openalex / crossref / github` keys. Both are accepted; runner
    normalizes.

===================== JSON SCHEMA =====================
{
  "rounds": [
    {
      "round": 1,
      "name": "broad_recall",
      "goal": "wide initial sweep across paper + repo backends",
      "calls": [
        {
          "tool": "search_arxiv | search_openalex | search_crossref | search_github",
          "query": "<phrase, ≤ 6 words; ≤ 4 for github>",
          "target_role": "baseline_or_parallel_paper | survey | reference | repo | dataset",
          "why_call": "<one-sentence reason this call belongs in this round>",
          "expected_output": "paper | repo | dataset",
          "fallback_tool": "<optional, search_*>"
        }
      ]
    },
    {
      "round": 2,
      "name": "reference_expansion",
      "goal": "expand coverage via benchmark / survey / recent-advances variants",
      "calls": []
    },
    {
      "round": 3,
      "name": "repo_dataset_followup",
      "goal": "find runnable code + datasets for the topic",
      "calls": []
    }
  ],
  "arxiv_queries":      ["<legacy key; copied from round 1 calls>"],
  "openalex_queries":   ["<legacy key; copied from round 1 calls>"],
  "crossref_queries":   ["<legacy key; copied from round 1 calls>"],
  "github_queries":     ["<legacy key; copied from round 1 calls>"],
  "year_min": 2018,
  "top_k_per_adapter": 8,
  "site_keywords": []
}

===================== ANTI-PATTERNS =====================
- Round 1 with no arxiv call (arxiv is the spine).
- Round 2 / 3 with no calls (you must plan something for each round).
- A github query of 5+ words (returns zero hits).
- A query that mentions an exact paper / repo title.
- A `target_role` outside the allowed set.
- More than 4 calls per round (runner's per-round cooldown).
"""

USER_TEMPLATE_PLAN_TOOLS = """\
PARSED TOPIC:
{topic_json}

Emit the multi-round call plan JSON now.
"""


# Backwards-compat alias used by the Re01 research_agent._chat_json_strict.
# Kept so test_s66v_agent.py + any legcy callers still find the symbol.
SEARCH_PLAN_SYSTEM = PLAN_TOOLS_SYSTEM
