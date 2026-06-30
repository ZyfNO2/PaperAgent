# Task T1 Report: keyword_match_explainer.py

## Status: DONE

## What was implemented

Created `apps/api/app/services/retrieval/keyword_match_explainer.py` with:

**Data model (1 Pydantic class):**
- `KeywordMatchExplanation` — `candidate_id`, `matched_topic_keywords`, `matched_related_keywords`, `missing_required_keywords`, `unrelated_keywords`, `match_summary`, `evidence_gap` (Literal 8 values)

**Public functions:**
- `explain_keyword_match(candidate: dict, topic_atoms: dict) -> KeywordMatchExplanation`
- `explain_candidates(candidates: list[dict], topic_atoms: dict) -> list[KeywordMatchExplanation]`

**Internal helpers:**
- `_atom_pattern(atom)` — word-boundary-aware, case-insensitive regex; handles CJK without `\b`
- `_count_atoms_in_text(atoms, text)` — returns matching atoms, dedup by lowercase, preserve order
- `_detect_unrelated(text)` — scans for cross-domain hint tokens (`survey motivation`, `german coding`, `mlperf`, `ct scan`, etc.)
- `_detect_evidence_gap(...)` — priority: `url_unverified` > `wrong_domain` (no text / no signal / strong cross-domain) > `dataset_missing` > `repo_missing` > `object_missing` > `method_missing` > `task_missing` > `none`
- `_format_match_summary(...)` — Chinese display string with `命中 / 相关 / 缺失 / 疑似无关 / 结论` sections

## Rules honored
- No network calls (zero imports outside stdlib + pydantic)
- No LLM calls
- No 0-1 score output
- Does not change sort order — only annotates
- Word-boundary regex so `crack` does not match `crackpot`; multi-word atoms like `surface defect` match as a unit

## Test approach

`apps/api/tests/test_keyword_match_explainer.py` — 16 unit tests covering:
- Basic atom counting (3 cases incl. CJK + word boundary + case)
- Empty input safety
- Unrelated hint detection (survey/german vs clean)
- Gap detection priority (5 cases)
- End-to-end `explain_keyword_match` for happy / missing / unrelated / blank / url-failed paths

Run via pytest: 16 passed in 0.29s.
Run standalone: `python apps/api/tests/test_keyword_match_explainer.py` → OK: 16 / 16.

## Integration notes (for T5/T6 callers)

- Pure function over `dict` — no ORM, no FastAPI dependency
- Designed to be called after `candidate_cleaner.clean_candidates()` and before frontend rendering
- The frontend `RetrievalCandidatePanel` can render `match_summary` directly and replace the current `score {x.toFixed(2)}` badge

## Concerns

None. Self-contained, no new dependencies, no LLM cost, deterministic output.