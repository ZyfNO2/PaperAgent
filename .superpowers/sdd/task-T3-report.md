# Task T3 Report: research_query_builder.py

## Summary
Created `apps/api/app/services/research_query_builder.py` with multi-source query building for the research planner agent. LLM-first with rule-based fallback, domain-aware query pools, and minimum-query enforcement.

## Implementation

### Public API
- `build_query_pack(topic_parse: dict, max_queries: int = 40) -> dict` — primary entry; tries LLM, falls back to rule_fill_query_pack, ensures domain coverage, ensures minimum 18 queries, truncates to max_queries.
- `rule_fill_query_pack(topic_parse: dict) -> dict` — fallback rule-based pack builder using domain-specific query pools.
- `ensure_minimum_queries(query_pack: dict, min_total: int = 18) -> dict` — pads short buckets using positive_methods and domain templates.

### Domain-Aware Logic
Per-domain pools in `_DOMAIN_QUERY_POOLS`:
- **vision_3d**: COLMAP, MVSNet, OpenPCDet, PointNet++, VoteNet, 3D Gaussian Splatting, DUSt3R, FoundationStereo, NeRF, PointRCNN
- **vision_2d**: YOLO, Faster R-CNN, Mask R-CNN, ViT, U-Net, ResNet (datasets: NEU-DET, GC10-DET, MVTec AD)
- **nlp_llm**: BERT, RoBERTa, LLM, LoRA, RAG, ChatGPT (datasets: ChnSentiCorp, THUCNews)
- **signal_timeseries / robotics_control**: smaller pools with domain-appropriate methods.

### Hard-Rule Enforcement
1. **≥18 queries**: `ensure_minimum_queries` pads from `positive_methods` and domain templates until total ≥ min_total (default 18).
2. **No "ultralytics yolov8 defect detection" pollution**: queries are templated from `topic_parse.query_atoms_en` + domain pool, never a fixed string.
3. **Domain-specific queries**: each query is composed from the topic's atoms + domain pool; tests verified:
   - 3D topic: includes 3D Gaussian Splatting, DUSt3R; NO YOLO.
   - YOLO steel: NO 3DGS, DUSt3R, COLMAP.
   - NLP sentiment: includes BERT, RoBERTa; NO YOLO, PointNet.
4. **Query length 3-8 words**: enforced via `3 <= len(q.split()) <= 8` filter in rule_fill_query_pack.
5. **Negative queries**: `_build_negative_filters` derives negative filters from `topic_parse.negative_domains` (already domain-correct from T2).

### LLM Integration
- Uses `app.services.research_prompts.search_strategy_system()` and `.search_strategy_user()` for prompt templates.
- Calls `app.services.llm.chat_json()` with 30s timeout, 2000 max_tokens.
- Flattens LLM `search_strategies[]` buckets (core_papers, datasets, github_repos, classic_baselines, emerging_methods) into the flat ResearchQueryPack dict.
- Falls back to `rule_fill_query_pack` on `LLMUnavailable` or any other exception (logged as warning).

### Defense-in-Depth
`_ensure_domain_coverage` runs after LLM/rule pack is assembled but before `ensure_minimum_queries`. It scans for domain-critical methods (3DGS, DUSt3R for vision_3d; BERT, RoBERTa for nlp_llm) using case-insensitive alias matching, and injects missing ones into `repo_queries` so retrieval will surface the right evidence even when the LLM oversimplifies.

## Self-Check Results

Ran `python -m app.services.research_query_builder` (assert-based __main__ demo):

```
T3 self-check passed: 3D=34, YOLO=29, NLP=31
```

(LLM timed out on first run, rule-based path produced 34/29/31 queries respectively. Second run with LLM success produced 3D=33, still passing all golden-case assertions.)

### Golden Cases Verified
1. **3D topic** ("基于三维成像的损伤智能检测"): 33-34 queries; includes "3D Gaussian Splatting" (or "3DGS") and "DUSt3R"; does NOT contain "YOLO".
2. **YOLO steel** ("基于YOLO的钢材表面缺陷检测"): 29 queries; does NOT contain "3DGS", "3D Gaussian Splatting", "DUSt3R", or "COLMAP".
3. **NLP sentiment** ("基于大语言模型的中文舆情情感分析"): 31 queries; includes "BERT" and "RoBERTa"; does NOT contain "YOLO" or "PointNet".

## Files Modified
- **Created**: `apps/api/app/services/research_query_builder.py` (~590 lines including __main__ self-check)

## Integration Points
- Imports: `app.services.llm.chat_json`, `app.services.research_prompts.{search_strategy_system, search_strategy_user, SEARCH_STRATEGY_SCHEMA}`
- Used by: future T4 (research_planner_agent or similar orchestrator) will call `build_query_pack(topic_parse)` after topic parsing.

## Known Limitations
- LLM call uses fixed 30s timeout — may need retry/circuit-breaker in production.
- Priority injection caps at 5 missing methods to avoid bloating `repo_queries`.
- Domain coverage check uses simple substring matching; if a method appears as part of a compound word (e.g., "foundationstereodepth") it would still match — acceptable for retrieval purposes.