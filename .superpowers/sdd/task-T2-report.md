# Task T2 Report: web_dataset_search.py

## Status: DONE

## What was implemented
Created `apps/api/app/services/retrieval/web_dataset_search.py` with:

**Data structure (`WebDatasetResult`, Pydantic BaseModel):**
- `dataset_id`, `name`, `source` (Literal: websearch/mendeley/zenodo/roboflow/kaggle/paperswithcode), `url`, `scale`, `license`, `task_type`, `matched_query`, `is_downloadable`, `needs_auth`.

**Query templates (`DATASET_QUERY_TEMPLATES`):**
11 templates: ZH (`{object_cn} 数据集` / `缺陷 检测` / `裂缝`), EN (`{object_en} dataset` / `crack detection` / `defect detection`), and 5 site: prefixes (Mendeley / Zenodo / Kaggle / Roboflow / PapersWithCode).

**Public API (4 functions):**
- `search_web_datasets(topic_atoms, domain, min_results, search_payloads=None) -> list[WebDatasetResult]` — main entry. Uses caller-supplied `(url, html)` payloads when given; falls back to `seed_known_datasets` when no payloads are passed.
- `_build_dataset_queries(topic_atoms) -> list[str]` — formats templates with object_cn/object_en, skips slots that are empty.
- `_parse_web_result(url, html) -> WebDatasetResult | None` — regex-based extraction of `<title>`, `X images/samples`, and `CC BY / MIT / Apache` license. No real network.
- `_should_trigger(topic_atoms, current_candidates, min_results=2, min_top_score=0.45) -> bool` — triggers when: candidate count < 2, top score < 0.45, placeholder `(未匹配公开数据集)` appears, or engineering objects present with zero dataset candidates.

**Seed fallback (`seed_known_datasets`):**
Returns curated list of 7 known public dataset URLs (SDNET2018, Mendeley Concrete Crack Images + Segmentation, CODEBRIM, Roboflow Concrete Crack, Kaggle SDNET2018, duplicate Mendeley entry). Filtered by `concrete/crack/混凝土/裂缝/损伤/damage` keyword match.

**URL → source inference (`_infer_source`):**
8 regex patterns covering Mendeley, Zenodo, Roboflow, Kaggle, PapersWithCode, USU Digital Commons, GitHub, HuggingFace datasets. Defaults to `websearch`.

**Trace hook (`trace_search`):**
Optional import-by-need `append_trace` from `..trace_store`. Writes `web_dataset_search` action with first 3 queries, result count, and source distribution. Guarded with try/except so absence of trace_store doesn't break the module.

## Test approach
Embedded `__main__` self-check (9 assertions, all pass):
- `_should_trigger`: empty → True; placeholder hit → True; 2 high-score candidates → False.
- `_build_dataset_queries`: ≥ 5 queries returned.
- `seed_known_datasets`: concrete atoms → ≥ 2 seed results.
- `_infer_source`: mendeley/zenodo/roboflow URLs each map correctly.
- `_parse_web_result`: empty url → None; valid HTML extracts scale + license.
- `search_web_datasets`: no payload → 4 seed results, all have URLs.

Run: `cd apps/api && python -m app.services.retrieval.web_dataset_search` → `OK web_dataset_search self-check passed (queries=11 seed=4 parsed=4)`.

## Concerns
- `_parse_web_result` only extracts a few regex fields (title/scale/license). Sufficient for known Mendeley/Zenodo/Roboflow listings; real Kaggle/HTML may need richer parsing in a follow-up.
- Module does no real HTTP. Caller (`orchestrator.py` integration in T5) must supply `search_payloads` from a real WebSearch API or accept the seed fallback.
- The seed list is concrete-crack-specific; other engineering objects will fall through to empty `seed_known_datasets` until more domains are curated. Tracked for future expansion.

## Integration
This is a fallback. T5 (`orchestrator.py` integration) will call `search_web_datasets` inside the gap-report retry loop when `_should_trigger(...)` returns True. Results feed back into the candidate normalizer and dedupe before UI display.
