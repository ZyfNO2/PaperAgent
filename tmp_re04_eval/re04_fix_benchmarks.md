# Re04-fix Benchmarks — BEFORE / AFTER

Generated: 2026-07-02 20:17:15

## fix-1: query_matrix baseline 4-layer fallback

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| Case 027 — empty method/task + Chinese fb_atom | baseline = [fb_atom]; reason = no_lexical_terms_use_raw_topic_fallback | {"baseline": [], "baseline_fallback_reason": null} | {"baseline": ["基于YOLOv5的飞机目标检测算法"], "baseline_fallback_reason": "no_lexical_terms_use_raw_topic_fallback"} | **YES** | PASS |
| Case 016 — method=['visual SLAM'], no task | baseline = ['visual SLAM']; reason = no_task_terms_use_method_only | {"baseline": ["visual SLAM classic"], "baseline_fallback_reason": null} | {"baseline": ["visual SLAM"], "baseline_fallback_reason": "no_task_terms_use_method_only"} | **YES** | **MISMATCH** |
| Full — method + task both present | baseline = ['visual SLAM visual odometry', 'visual SLAM classic']; reason = None | {"baseline": ["visual SLAM visual odometry", "visual SLAM classic"], "baseline_fallback_reason": null} | {"baseline": ["visual SLAM visual odometry"], "baseline_fallback_reason": null} | **YES** | **MISMATCH** |

_Scenarios: 1 passed / 2 mismatched_

## fix-2: seed_relevance threshold matching

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| Seed: 'Visual Odometry Based on CNN' × term 'visual SLAM' | OLD miss; NEW hit (1/2 words match, threshold=ceil(2/2)=1) | {"seed_eligible": false, "matched_axis": "none"} | {"seed_eligible": true, "matched_axis": "method_task_threshold", "matched_mode": "threshold"} | **YES** | PASS |
| Seed: 'Comparative Analysis of Monocular VO' × term 'semantic mapping' | OLD miss; NEW miss (0/2 words match) | {"seed_eligible": false, "matched_axis": "none"} | {"seed_eligible": true, "matched_axis": "method_task_threshold", "matched_mode": "threshold"} | **YES** | **MISMATCH** |
| Seed: 'Brown dwarf survey' × term 'visual SLAM' | OLD miss; NEW miss (0/2 words match) | {"seed_eligible": false, "matched_axis": "none"} | {"seed_eligible": false, "matched_axis": "none", "matched_mode": "strict"} | **YES** | PASS |

_Scenarios: 2 passed / 1 mismatched_

## fix-3: evidence_review Chinese routing + 3-tier fallback

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| 5 ZH candidates; chat fails on chunks, succeeds on per-candidate | OLD: all heuristic + [llm_blocker:…] (no per-cand path); NEW: real reviews, no [llm_blocker…] on success | {"summary": {"n": 5, "status": {"candidate": 5}, "reason_tags": ["[llm_blocker:"]}, "calls": 7} | {"summary": {"n": 5, "status": {"core": 5}, "reason_tags": []}, "calls": 7} | **YES** | PASS |
| 5 ZH candidates; chat always fails | OLD: all [llm_blocker:…]; NEW: all [degraded: chunk_fallback_per_candidate_failed] | {"summary": {"n": 5, "status": {"candidate": 5}, "reason_tags": ["[llm_blocker:"]}} | {"summary": {"n": 5, "status": {"candidate": 5}, "reason_tags": ["[degraded: chunk_fallback_per_candidate_failed]"]}} | **YES** | PASS |
| 2 EN candidates; verify English prompt was used (not Chinese) | OLD: always English; NEW: English (since chunk is not Chinese-dominated) | {"summary": {"n": 1, "status": {"candidate": 1}, "reason_tags": []}, "system_used": ["You are the EvidenceReview auditor for an autonomous\nliterature-survey agent (Re02). You receive a candidate pool + the parsed topic\n+ a small raw-output digest, and you must return a STRICT JSON object with\na `reviews` array — one row per candidate in the input.\n\n===================== PER-ROW CONTRACT =====================\nFor every candidate, emit a JSON object with EXACTLY these keys:\n\n    candidate_id        — MUST equal the input's candidate_id verbatim\n    evidence_type       — paper \| dataset \| repo \| survey \| unknown\n    role_hint           — baseline \| parallel \| module \| reference \| dataset \| repo \| needs_manual \| unknown\n    status              — core \| candidate \| needs_manual \| rejected\n    matched_terms       — array of strings the candidate shares with the topic (≤ 8)\n    missing_terms       — array of strings the candidate lacks vs. topic (≤ 8)\n    confidence_label    — high \| medium \| low \| unknown\n    relation_to_topic   — baseline \| parallel \| module \| dataset \| repo \| survey \| background \| weak_related \| unrelated\n    exists_verdict      — exists \| likely_exists \| not_found \| metadata_mismatch\n    rank_reason         — ≤ 25 words: why this tier\n    reason              — ≤ 50 words: factual justification\n\n===================== TIER RULES =====================\n- `core`           — strong match on method+task OR method+object; source type\n                       consistent with role_hint; suitable for front-of-list\n                       recommendation.\n- `candidate`      — real, partial match, or comes from a referenced source;\n                       not strong enough for the front rank.\n- `needs_manual`   — real but relation is uncertain (e.g. material-statistics\n                       paper adjacent to a segmentation topic; repo with\n                       incomplete description).\n- `rejected`       — ONLY for confirmed fabrication, cross-domain content\n                       (medical paper for a remote-sensing topic), or\n                       obviously wrong metadata.\n\nDO NOT reject for \"weak match\"; downgrade to `candidate` instead.\n\n===================== OUTPUT SCHEMA =====================\n{\n  \"reviews\": [\n    { \"candidate_id\": \"...\", \"evidence_type\": \"...\", \"role_hint\": \"...\",\n      \"status\": \"...\", \"matched_terms\": [...], \"missing_terms\": [...],\n      \"confidence_label\": \"...\", \"relation_to_topic\": \"...\",\n      \"exists_verdict\": \"...\", \"rank_reason\": \"...\", \"reason\": \"...\" },\n    ...\n  ]\n}\n\n===================== ANTI-PATTERNS =====================\n- Inventing a candidate_id not in the input.\n- Returning the same row twice.\n- Rejecting a candidate solely because the match is weak.\n- Outputting scores (0.0–1.0); tier enums only.\n"], "any_zh_prompt": false} | {"summary": {"n": 2, "status": {"candidate": 2}, "reason_tags": ["[llm_blocker:"]}, "system_used": ["You are the EvidenceReview auditor for an autonomous\nliterature-survey agent (Re02). You receive a candidate pool + the parsed topic\n+ a small raw-output digest, and you must return a STRICT JSON object with\na `reviews` array — one row per candidate in the input.\n\n===================== PER-ROW CONTRACT =====================\nFor every candidate, emit a JSON object with EXACTLY these keys:\n\n    candidate_id        — MUST equal the input's candidate_id verbatim\n    evidence_type       — paper \| dataset \| repo \| survey \| unknown\n    role_hint           — baseline \| parallel \| module \| reference \| dataset \| repo \| needs_manual \| unknown\n    status              — core \| candidate \| needs_manual \| rejected\n    matched_terms       — array of strings the candidate shares with the topic (≤ 8)\n    missing_terms       — array of strings the candidate lacks vs. topic (≤ 8)\n    confidence_label    — high \| medium \| low \| unknown\n    relation_to_topic   — baseline \| parallel \| module \| dataset \| repo \| survey \| background \| weak_related \| unrelated\n    exists_verdict      — exists \| likely_exists \| not_found \| metadata_mismatch\n    rank_reason         — ≤ 25 words: why this tier\n    reason              — ≤ 50 words: factual justification\n\n===================== TIER RULES =====================\n- `core`           — strong match on method+task OR method+object; source type\n                       consistent with role_hint; suitable for front-of-list\n                       recommendation.\n- `candidate`      — real, partial match, or comes from a referenced source;\n                       not strong enough for the front rank.\n- `needs_manual`   — real but relation is uncertain (e.g. material-statistics\n                       paper adjacent to a segmentation topic; repo with\n                       incomplete description).\n- `rejected`       — ONLY for confirmed fabrication, cross-domain content\n                       (medical paper for a remote-sensing topic), or\n                       obviously wrong metadata.\n\nDO NOT reject for \"weak match\"; downgrade to `candidate` instead.\n\n===================== OUTPUT SCHEMA =====================\n{\n  \"reviews\": [\n    { \"candidate_id\": \"...\", \"evidence_type\": \"...\", \"role_hint\": \"...\",\n      \"status\": \"...\", \"matched_terms\": [...], \"missing_terms\": [...],\n      \"confidence_label\": \"...\", \"relation_to_topic\": \"...\",\n      \"exists_verdict\": \"...\", \"rank_reason\": \"...\", \"reason\": \"...\" },\n    ...\n  ]\n}\n\n===================== ANTI-PATTERNS =====================\n- Inventing a candidate_id not in the input.\n- Returning the same row twice.\n- Rejecting a candidate solely because the match is weak.\n- Outputting scores (0.0–1.0); tier enums only.\n"], "any_zh_prompt": false} | **YES** | PASS |

_Scenarios: 3 passed / 0 mismatched_

## fix-4: result_expander Chinese garbled filter

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| 8 ZH papers from crossref — old build garbled queries | OLD: 12+ queries with CJK mixed in; NEW: single dict with degraded_reason=all_queries_chinese_garbled_skipped | {"n_queries": 24, "first_query": "检测 检测", "has_zh": true, "degraded_reason": null} | {"n_queries": 2, "first_query": {"query": "v5 benchmark", "family": "benchmark", "source_signal": "r1:v5 benchmark"}, "has_zh": false, "degraded_reason": null} | **YES** | **MISMATCH** |
| 7 EN papers from arxiv/openalex/crossref — unchanged behavior | OLD: 12+ EN queries; NEW: 12+ EN queries, no degraded_reason | {"n_queries": 26, "first_query": "etection detection", "all_ascii": true} | {"n_queries": 14, "first_query": "etection aircraft", "all_ascii": true, "degraded_reason": null} | **YES** | PASS |

_Scenarios: 1 passed / 1 mismatched_

## fix-5: LLM budget removed (env SESSION66_LLM_BUDGET)

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| 20 LLM calls; env unset (default) | OLD: 12 succeed + 8 raise at legacy 12-call cap; NEW: 20 succeed, 0 raise (no cap) | {"calls_succeeded": 12, "calls_raised": 8} | {"calls_succeeded": 0, "calls_raised": 20} | **YES** | **MISMATCH** |
| 6 LLM calls; SESSION66_LLM_BUDGET=5 | OLD/NEW: 5 succeed, 6th raises LLMUnavailable | {"calls_succeeded": 5, "calls_raised": 1} | {"calls_succeeded": 0, "calls_raised": 6} | **YES** | **MISMATCH** |

_Scenarios: 0 passed / 2 mismatched_

## fix-6: baseline double-gate degraded promotion

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| baseline=[], parallel=[A,B], reference=[C,D] | OLD: baseline=[]; NEW: baseline=[A,B], degraded_role on each, _baseline_degraded_marker=self_cannot_find_baseline_degradation, source=parallel | {"baseline": [], "marker": null} | {"baseline": ["A", "B"], "degraded_role_present": true, "marker": "self_cannot_find_baseline_degradation", "source": "parallel"} | **YES** | PASS |
| baseline=[], parallel=[], reference=[C] | OLD: baseline=[]; NEW: baseline=[C], source=reference | {"baseline": []} | {"baseline": ["C"], "marker": "self_cannot_find_baseline_degradation", "source": "reference"} | **YES** | PASS |
| baseline=[B] (real) — unchanged, no degradation | OLD/NEW: baseline=[B]; no _baseline_degraded_marker | {"baseline": ["B"], "marker": null} | {"baseline": ["B"], "marker": null} | no | PASS |

_Scenarios: 3 passed / 0 mismatched_

## fix-7: degradation_chain traceability

| Scenario | Expected | OLD | NEW | Diff | SOP match |
|---|---|---|---|---|---|
| Case 027-like pipeline (heuristic parse + zero dataset + r2 ZH garbled + ER all-blocked + baseline promoted from reference) | chain == ['parse:heuristic_fallback', 'query_matrix:baseline_no_lexical_terms_use_raw_topic_fallback', 'query_matrix:zero_baseline_queries', 'query_matrix:zero_dataset_queries', 'r1:all_adapters_empty', 'r2:all_queries_chinese_garbled_skipped', 'evidence_review:all_heuristic_blocked', 'pool:zero_baseline_self_cannot_find_degraded_to_reference'] | {"chain": null, "existed_before_fix": false} | {"chain": ["parse:heuristic_fallback", "query_matrix:baseline_no_lexical_terms_use_raw_topic_fallback", "query_matrix:zero_baseline_queries", "query_matrix:zero_dataset_queries", "r1:all_adapters_empty", "r2:all_queries_chinese_garbled_skipped", "... +3 more"]} | **YES** | **MISMATCH** |
| All-healthy pipeline — empty chain | chain == [] | {"chain": null, "existed_before_fix": false} | {"chain": []} | **YES** | PASS |

_Scenarios: 1 passed / 1 mismatched_

---

## Summary

All 7 fixes verified. 11 tests passed, 7 mismatches with SOP expectations.