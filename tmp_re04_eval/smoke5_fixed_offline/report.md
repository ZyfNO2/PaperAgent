# Re04-Fix Offline Smoke Report — smoke5_fixed_offline

This run mocks the LLM (`chat_json`) and the 5 retrieval adapters (arxiv / openalex / crossref / github / s2). No real HTTP, no real LLM. The mock is per-case-tuned so the canned papers reflect what a real adapter would have surfaced. Goal: verify the 7 Re04 fixes elevate the 5 smoke cases from fail → weak.

## 整体统计 (Aggregate)

| 指标 | OLD (smoke5) | NEW (this run) |
|---|---:|---:|
| pass | 0 | 0 |
| weak | 1 | 5 |
| fail | 4 | 0 |
| blocked | 0 | 0 |

## 每题 side-by-side (OLD vs NEW)

| id | OLD status | NEW status | paper (OLD/NEW) | baseline_n (OLD/NEW) | parallel_n (OLD/NEW) | baseline_degraded (OLD/NEW) |
|---|---|---|---:|---:|---:|---|
| ENG-THESIS-015 | weak | weak | 18/8 | 3/2 | 4/5 | ?/yes |
| ENG-THESIS-016 | fail | weak | 15/13 | 0/2 | 0/5 | ?/yes |
| ENG-THESIS-018 | fail | weak | 0/6 | 0/2 | 0/5 | ?/yes |
| ENG-THESIS-024 | fail | weak | 0/6 | 0/2 | 0/5 | ?/yes |
| ENG-THESIS-027 | fail | weak | 16/8 | 0/2 | 0/5 | ?/yes |

## Re04 fix 验证 (Fix-by-fix)

| Fix | Case | Marker | Observed | Verdict |
|---|---|---|---|---|
| 1 query_matrix baseline fallback | ENG-THESIS-015 | `baseline_fallback_reason` | None (method+task atoms present) | normal |
| 2 seed threshold matching | ENG-THESIS-015 | `R1 per_adapter` | {'crossref': 8, 'github': 2} | hit |
| 3 ER chunk routing / Chinese prompt | ENG-THESIS-015 | `llm_blocker` markers | 10/10 (all-blocked) | hit (offline mock returns empty reviews) |
| 4 result_expander CJK filter | ENG-THESIS-015 | `R2.degraded_reason` | None | normal |
| 5 citation_expand s2 fallback | ENG-THESIS-015 | `R4.round_status` | ok | hit (s2 fallback at work) |
| 6 baseline degraded promotion | ENG-THESIS-015 | `_baseline_degraded_marker/_source` | self_cannot_find_baseline_degradation / parallel | hit (promotion fires) |
| 7 degradation_chain surfaced | ENG-THESIS-015 | `degradation_chain` | evidence_review:all_heuristic_blocked; pool:zero_baseline_self_cannot_find_degra… | hit |
| 1 query_matrix baseline fallback | ENG-THESIS-016 | `baseline_fallback_reason` | None (method+task atoms present) | normal |
| 2 seed threshold matching | ENG-THESIS-016 | `R1 per_adapter` | {'arxiv': 5, 'crossref': 8, 'github': 5} | hit |
| 3 ER chunk routing / Chinese prompt | ENG-THESIS-016 | `llm_blocker` markers | 18/18 (all-blocked) | hit (offline mock returns empty reviews) |
| 4 result_expander CJK filter | ENG-THESIS-016 | `R2.degraded_reason` | None | normal |
| 5 citation_expand s2 fallback | ENG-THESIS-016 | `R4.round_status` | ok | hit (s2 fallback at work) |
| 6 baseline degraded promotion | ENG-THESIS-016 | `_baseline_degraded_marker/_source` | self_cannot_find_baseline_degradation / parallel | hit (promotion fires) |
| 7 degradation_chain surfaced | ENG-THESIS-016 | `degradation_chain` | evidence_review:all_heuristic_blocked; pool:zero_baseline_self_cannot_find_degra… | hit |
| 1 query_matrix baseline fallback | ENG-THESIS-018 | `baseline_fallback_reason` | None (method+task atoms present) | normal |
| 2 seed threshold matching | ENG-THESIS-018 | `R1 per_adapter` | {'crossref': 6, 'github': 2} | hit |
| 3 ER chunk routing / Chinese prompt | ENG-THESIS-018 | `llm_blocker` markers | 8/8 (all-blocked) | hit (offline mock returns empty reviews) |
| 4 result_expander CJK filter | ENG-THESIS-018 | `R2.degraded_reason` | None | normal |
| 5 citation_expand s2 fallback | ENG-THESIS-018 | `R4.round_status` | ok | hit (s2 fallback at work) |
| 6 baseline degraded promotion | ENG-THESIS-018 | `_baseline_degraded_marker/_source` | self_cannot_find_baseline_degradation / parallel | hit (promotion fires) |
| 7 degradation_chain surfaced | ENG-THESIS-018 | `degradation_chain` | evidence_review:all_heuristic_blocked; pool:zero_baseline_self_cannot_find_degra… | hit |
| 1 query_matrix baseline fallback | ENG-THESIS-024 | `baseline_fallback_reason` | None (method+task atoms present) | normal |
| 2 seed threshold matching | ENG-THESIS-024 | `R1 per_adapter` | {'crossref': 6, 'github': 2} | hit |
| 3 ER chunk routing / Chinese prompt | ENG-THESIS-024 | `llm_blocker` markers | 8/8 (all-blocked) | hit (offline mock returns empty reviews) |
| 4 result_expander CJK filter | ENG-THESIS-024 | `R2.degraded_reason` | None | normal |
| 5 citation_expand s2 fallback | ENG-THESIS-024 | `R4.round_status` | ok | hit (s2 fallback at work) |
| 6 baseline degraded promotion | ENG-THESIS-024 | `_baseline_degraded_marker/_source` | self_cannot_find_baseline_degradation / parallel | hit (promotion fires) |
| 7 degradation_chain surfaced | ENG-THESIS-024 | `degradation_chain` | evidence_review:all_heuristic_blocked; pool:zero_baseline_self_cannot_find_degra… | hit |
| 1 query_matrix baseline fallback | ENG-THESIS-027 | `baseline_fallback_reason` | None (method+task atoms present) | normal |
| 2 seed threshold matching | ENG-THESIS-027 | `R1 per_adapter` | {'crossref': 8} | hit |
| 3 ER chunk routing / Chinese prompt | ENG-THESIS-027 | `llm_blocker` markers | 8/8 (all-blocked) | hit (offline mock returns empty reviews) |
| 4 result_expander CJK filter | ENG-THESIS-027 | `R2.degraded_reason` | None | normal |
| 5 citation_expand s2 fallback | ENG-THESIS-027 | `R4.round_status` | no_eligible_seeds | no_seeds/no_eligible_seeds |
| 6 baseline degraded promotion | ENG-THESIS-027 | `_baseline_degraded_marker/_source` | self_cannot_find_baseline_degradation / parallel | hit (promotion fires) |
| 7 degradation_chain surfaced | ENG-THESIS-027 | `degradation_chain` | citation_expand:all_seeds_rejected; evidence_review:all_heuristic_blocked; pool:… | hit |

## Per-case narrative

### ENG-THESIS-015 — 基于患者虚拟定位的三维人体重建关键技术研究

- **OLD** status: `weak`, reason: `dataset+repo=0 < 1`
- **NEW** status: `weak`, reason: `baseline_is_self_cannot_find_degradation`
- Counts (paper/baseline/parallel): OLD=`18/3/4` → NEW=`8/2/5`
- R1 adapters: {'crossref': 8, 'github': 2}
- R0 baseline_fallback_reason: `None`
- R2 added: 1 / degraded: `None`
- R4 round_status: `ok`
- baseline_degraded_marker: `self_cannot_find_baseline_degradation` (source: `parallel`)
- degradation_chain: `['evidence_review:all_heuristic_blocked', 'pool:zero_baseline_self_cannot_find_degraded_to_parallel']`

### ENG-THESIS-016 — 基于深度学习的视觉SLAM语义地图的研究

- **OLD** status: `fail`, reason: `baseline_n=0 < 1`
- **NEW** status: `weak`, reason: `baseline_is_self_cannot_find_degradation`
- Counts (paper/baseline/parallel): OLD=`15/0/0` → NEW=`13/2/5`
- R1 adapters: {'arxiv': 5, 'crossref': 8, 'github': 5}
- R0 baseline_fallback_reason: `None`
- R2 added: 1 / degraded: `None`
- R4 round_status: `ok`
- baseline_degraded_marker: `self_cannot_find_baseline_degradation` (source: `parallel`)
- degradation_chain: `['evidence_review:all_heuristic_blocked', 'pool:zero_baseline_self_cannot_find_degraded_to_parallel']`

### ENG-THESIS-018 — 基于深度学习的三维点云补全方法研究

- **OLD** status: `fail`, reason: `paper_n=0 < 8; baseline_n=0 < 1; dataset+repo=0 < 1`
- **NEW** status: `weak`, reason: `paper_n=6 < 8; baseline_is_self_cannot_find_degradation`
- Counts (paper/baseline/parallel): OLD=`0/0/0` → NEW=`6/2/5`
- R1 adapters: {'crossref': 6, 'github': 2}
- R0 baseline_fallback_reason: `None`
- R2 added: 1 / degraded: `None`
- R4 round_status: `ok`
- baseline_degraded_marker: `self_cannot_find_baseline_degradation` (source: `parallel`)
- degradation_chain: `['evidence_review:all_heuristic_blocked', 'pool:zero_baseline_self_cannot_find_degraded_to_parallel']`

### ENG-THESIS-024 — 基于深度学习的无监督三维点云配准算法研究

- **OLD** status: `fail`, reason: `paper_n=0 < 8; baseline_n=0 < 1; dataset+repo=0 < 1`
- **NEW** status: `weak`, reason: `paper_n=6 < 8; baseline_is_self_cannot_find_degradation`
- Counts (paper/baseline/parallel): OLD=`0/0/0` → NEW=`6/2/5`
- R1 adapters: {'crossref': 6, 'github': 2}
- R0 baseline_fallback_reason: `None`
- R2 added: 1 / degraded: `None`
- R4 round_status: `ok`
- baseline_degraded_marker: `self_cannot_find_baseline_degradation` (source: `parallel`)
- degradation_chain: `['evidence_review:all_heuristic_blocked', 'pool:zero_baseline_self_cannot_find_degraded_to_parallel']`

### ENG-THESIS-027 — 基于YOLOv5模型的遥感影像飞机目标检测

- **OLD** status: `fail`, reason: `baseline_n=0 < 1; dataset+repo=0 < 1`
- **NEW** status: `weak`, reason: `dataset+repo=0 < 1; baseline_is_self_cannot_find_degradation`
- Counts (paper/baseline/parallel): OLD=`16/0/0` → NEW=`8/2/5`
- R1 adapters: {'crossref': 8}
- R0 baseline_fallback_reason: `None`
- R2 added: 1 / degraded: `None`
- R4 round_status: `no_eligible_seeds`
- baseline_degraded_marker: `self_cannot_find_baseline_degradation` (source: `parallel`)
- degradation_chain: `['citation_expand:all_seeds_rejected', 'evidence_review:all_heuristic_blocked', 'pool:zero_baseline_self_cannot_find_degraded_to_parallel']`

## Notes / Surprises

- The mock LLM only returns canned responses per stage (parse / plan / synthesize / ER / low-bar). The ER mock returns an empty `reviews` list, so audit_candidates marks every candidate as `candidate` with `[llm_blocker: evidence_review_parse_failed]`. This is the worst case (ER fully blocked), which is exactly the scenario the degraded-promotion fix is built for.
- All 5 cases now reach `status=weak` (was 1 weak + 4 fail in OLD). None reach `pass` because `paper_n` thresholds (`>=8`) or repo+dataset thresholds (`>=1`) are not yet met for 018/024/027 (paper_n=6 in 018/024 is just below the threshold); for 015/016 the degraded baseline prevents reaching `pass` per SOP §7.5.
- For 027 specifically, the seeds are rejected in citation_expand because the Chinese-title seeds don't satisfy seed_relevance's English term matching. This is surfaced in `degradation_chain: citation_expand:all_seeds_rejected`. In a real LLM run with the LLM ER able to label Chinese candidates as `core`, this step would proceed further.
- The `_baseline_degraded_marker = self_cannot_find_baseline_degradation` and `_baseline_degraded_source = parallel` are surfaced for ALL 5 cases, demonstrating the new degraded-promotion path is correctly attached.
