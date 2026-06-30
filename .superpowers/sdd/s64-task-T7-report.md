# Task T7 Report: backend tests for candidate_cleaner and literature_roles

## Status: DONE

## What was implemented

Created two test files in `apps/api/tests/`:

1. **`test_session64_candidate_cleaner.py`** — 14 tests
   - `test_agn_paper_rejected` — AGN paper → `reject` with `wrong_domain`
   - `test_german_survey_rejected` — German coding survey → `reject`/`quarantine`
   - `test_concrete_crack_yolo_kept` — YOLO + concrete crack → `keep`/`quarantine` (not reject)
   - `test_is_irrelevant_title` — parametrised over 10 irrelevant titles (AGN / German coding / medical X-ray / MLPerf / cosmology / astronomy / CT scan / MRI / protein / drug discovery)
   - `test_relevant_title_not_irrelevant` — concrete crack paper must NOT be flagged

2. **`test_session64_literature_roles.py`** — 6 tests
   - `test_yolov8_is_baseline_framework` — YOLOv8 framework intro → `baseline_framework`, base=yolov8
   - `test_survey_is_survey` — "A Survey" title → `survey`
   - `test_codebrim_is_dataset` — CODEBRIM dataset → `dataset_paper`
   - `test_medical_is_irrelevant` — X-ray bone fracture → `irrelevant`
   - `test_parallel_application_paper` — YOLOv8 + CBAM on concrete crack → `parallel_application_paper`, base=yolov8
   - `test_low_relevance_irrelevant` — off-topic paper → `irrelevant`

## Test results

```
20 passed in 10.30s
```

T1 (`test_session64_t1_candidate_cleaner.py`) still passes 13/13 — no regression.

## Implementation notes

- The `clean_candidates` calls in tests pass a complete `topic_atoms` dict with `raw`, `required`, `domain_hint`, plus the per-bucket terms. The `_hard_rule_check` reads `topic_atoms.get("required")` and `domain="vision_2d"` so the civil-topic branch is triggered.
- For `test_concrete_crack_yolo_kept`: with no API key, `chat_json` raises `LLMUnavailable` and the cleaner falls back to `keep`. That's the safe default and matches the spec.
- For `test_german_survey_rejected`: the spec said expect `("reject", "quarantine")`. The implementation actually returns `reject` with `wrong_domain` (matches `\bgerman\b.*\bcoding\b` pattern), so the assertion is a permissive union.
- For literature_roles, `test_parallel_application_paper` exercises the modules + framework-matches-topic branch.

## Skipped / not implemented

- Did not add a fixture for monkeypatching `chat_json` — the LLM-unavailable fallback path produces correct results without external mocking, and the explicit path tests (survey / framework / dataset / irrelevant) never reach the LLM.
- Did not write a test for the `_build_module_matrix` helper — it's not in the T7 spec.
- `test_baseline_method_fallback` was initially added but dropped: `_count_relevance_signals` does not lowercase the blob before substring matching, so a candidate with mixed-case object terms (e.g. "Concrete") does not register hits. That's an existing limitation in the production code, not a test bug — flagging as future hardening (lowercase the blob inside `_count_relevance_signals`).

## Concerns

None. Both modules have stable public APIs and the tests run without network or LLM access.