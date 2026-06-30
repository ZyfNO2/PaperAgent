# Task T1 Report: research_prompts.py

## Status: DONE

## What was implemented
Created `apps/api/app/services/research_prompts.py` with:

**10 prompt functions (5 stages, system + user pairs):**
- `topic_understand_system()` / `topic_understand_user(raw_topic, student_context, local_case_hints)`
- `problem_decompose_system()` / `problem_decompose_user(topic_parse_json)`
- `search_strategy_system()` / `search_strategy_user(topic_parse_json, problem_decompose_json)`
- `candidate_screen_system()` / `candidate_screen_user(topic_parse_json, candidates_jsonl)`
- `direction_advice_system()` / `direction_advice_user(topic_parse_json, shortlist_json, gap_report_json)`

**5 schema template constants:**
- `TOPIC_UNDERSTAND_SCHEMA`
- `PROBLEM_DECOMPOSE_SCHEMA`
- `SEARCH_STRATEGY_SCHEMA`
- `CANDIDATE_SCREEN_SCHEMA`
- `DIRECTION_ADVICE_SCHEMA`

**1 shared constant:**
- `DOMAIN_ROUTES` (the 10-route enum embedded in topic_understand system prompt)

All prompt text is verbatim from the SOP brief. No modifications. All functions are exported at module level with docstrings.

## Test approach
No tests written. The module is pure prompt-string formatting — no logic, no I/O, no LLM calls. A single import smoke (`from app.services.research_prompts import ...`) confirms all 10 functions and the `DOMAIN_ROUTES` constant load without error.

## Concerns
None. The file is self-contained, has no runtime dependencies, and the f-string placeholders map directly to the variable names in the SOP. Downstream callers (`research_planner_agent.py`, not yet written) can import and call these directly.