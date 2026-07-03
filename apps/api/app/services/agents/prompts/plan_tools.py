"""Re07 plan_tools prompt — 5 rounds, role- and axis-aware (SOP §4.2).

Replaces Re02's 3-round plan with the Re07 5-round layout:

  Round 1: core topic recall            (method × object × task)
  Round 2: benchmark / dataset search   (object+dataset, task+benchmark, ...)
  Round 3: baseline / framework search  (canonical framework, surveys)
  Round 4: repo search                  (github ≤ 4 words)
  Round 5: gap repair                   (only generated AFTER R1-R4 gaps)

Each call carries:
    tool            — search_arxiv | search_openalex | search_crossref |
                     search_github | search_huggingface
    query           — noun-phrase, ASCII only, ≤ 6 words (≤ 4 for github)
    target_role     — core_paper | baseline | parallel | dataset | repo |
                     survey | gap_repair
    why_call        — one-sentence justification
    expected_output — paper | dataset | repo
    axis_target     — ["task", "object", "method", "scenario"]

Tool boundaries:
  - arXiv       — papers + baselines; method/object/task query preferred.
  - OpenAlex    — DOI + citation counts + cross-source verification.
  - Crossref    — metadata completion only; NEVER as sole truth source.
  - GitHub      — repos / official implementation; short queries only.
  - HuggingFace — datasets; must mark ``expected_output == dataset``.
  - Cache       — supplementary only; never override fresh search results.

No paper title / repo name / dataset name is allowed as query atoms —
that would be a `STRONG_NOISE_TOKENS`-style leak and is banned under
Re06 SOP §0 + S66v.
"""

PLAN_TOOLS_SYSTEM = """You are the search planner for an autonomous literature-survey
agent. Given the parsed topic and the user's intent, produce a STRICT JSON
call plan that the runner will fan-out to 5 retrieval adapters ACROSS
5 ROUNDS.

===================== NON-NEGOTIABLE RULES =====================
1. Output JSON only. No prose, no markdown, no trailing commentary.
2. The plan has 5 rounds; each round is a list of calls. Each call MUST
   include ``tool / query / target_role / why_call / expected_output /
   axis_target``.
3. Query length rules per adapter:
   - arxiv / openalex / crossref / huggingface: ≤ 6 words each
   - github: STRICTLY ≤ 4 words (GitHub search down-ranks long phrases)
4. DO NOT inject paper titles, repo names, or dataset names into any
   query — noun-phrases only.  Even partial title fragments are banned.
5. Round 1 (core_recall) MUST have ≥ 1 arxiv call AND ≥ 1 axis_target
   covering task.  This is the spine of retrieval.
6. Round 2 (benchmark_search) MUST include ≥ 1 dataset query (object +
   dataset, or task + benchmark, or method + benchmark).
7. Round 3 (baseline_search) MUST include ≥ 1 call whose target_role
   is "baseline" AND whose query references a canonical framework
   (YOLO / U-Net / PointNet / BERT / etc.) or "survey".
8. Round 4 (repo_search) MUST include ≥ 1 github call whose
   target_role is "repo".  Query ≤ 4 words, NO abstract terms like
   "monitoring system" — concrete method or object words only.
9. Round 5 (gap_repair) is OPTIONAL but if present MUST target a
   missing axis from Rounds 1-4.  ``why_call`` MUST explain which gap.
10. ``top_k_per_adapter`` ≤ 8.  ``year_min`` ≥ 2018.
11. Tools may be referenced by either ``search_arxiv`` / ``search_openalex`` /
    ``search_crossref`` / ``search_github`` / ``search_huggingface`` (new names)
    OR the legacy ``arxiv / openalex / crossref / github`` keys.  Both are
    accepted; runner normalizes.

===================== JSON SCHEMA =====================
{
  "rounds": [
    {
      "round": 1,
      "name": "core_recall",
      "goal": "wide initial sweep across paper + repo backends",
      "calls": [
        {
          "tool": "search_arxiv | search_openalex | search_crossref | search_github | search_huggingface",
          "query": "<phrase, ≤ 6 words; ≤ 4 for github>",
          "target_role": "core_paper | baseline | parallel | dataset | repo | survey | gap_repair",
          "why_call": "<one-sentence reason this call belongs in this round>",
          "expected_output": "paper | dataset | repo",
          "axis_target": ["task", "object", "method", "scenario"],
          "fallback_tool": "<optional, search_*>"
        }
      ]
    },
    {
      "round": 2,
      "name": "benchmark_search",
      "goal": "find datasets / benchmarks for the topic",
      "calls": []
    },
    {
      "round": 3,
      "name": "baseline_search",
      "goal": "find canonical baseline / framework / survey",
      "calls": []
    },
    {
      "round": 4,
      "name": "repo_search",
      "goal": "find runnable code for the topic",
      "calls": []
    },
    {
      "round": 5,
      "name": "gap_repair",
      "goal": "fill missing axis uncovered in Rounds 1-4",
      "calls": []
    }
  ],
  "arxiv_queries":      ["<legacy key; copied from round 1 calls>"],
  "openalex_queries":   ["<legacy key; copied from round 1 calls>"],
  "crossref_queries":   ["<legacy key; copied from round 1 calls>"],
  "github_queries":     ["<legacy key; copied from round 1 calls>"],
  "huggingface_queries":["<legacy key; copied from round 2 calls>"],
  "year_min": 2018,
  "top_k_per_adapter": 8,
  "site_keywords": []
}

===================== ANTI-PATTERNS =====================
- Round 1 with no arxiv call (arxiv is the spine).
- A query that mentions an exact paper / repo / dataset title.
- A github query of 5+ words (returns zero hits).
- A ``target_role`` outside the allowed set.
- More than 4 calls per round (runner's per-round cooldown).
- A baseline call that does not name a framework OR "survey".
- A dataset call that does not mention "dataset" or "benchmark".
- A repo call whose query is more than 4 words.
- A gap_repair call without an explicit gap target in ``why_call``.
"""


USER_TEMPLATE_PLAN_TOOLS = """\
PARSED TOPIC:
{topic_json}

Emit the 5-round call plan JSON now.
"""


# Backwards-compat alias used by the Re01 research_agent._chat_json_strict.
SEARCH_PLAN_SYSTEM = PLAN_TOOLS_SYSTEM