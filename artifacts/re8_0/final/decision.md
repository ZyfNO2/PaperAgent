# Re8.0 Close-the-Loop — Final Decision

**Date**: 2026-07-13
**SOP tag**: Re8.0
**Status**: ✅ Backend SOP closed. Tailor Prompt tuning and cross-domain expansion deferred to next iteration.

## What this SOP delivered

Re8.0 closed the four P0 and four P1 gaps that were blocking the core research-pipeline value chain from running end-to-end on real seed papers (DOI/arXiv):

1. **CandidateSeed input contract normalization** — `seed_resolver._classify_input` flattens `raw_input` onto top-level before classification; demo CASES write both forms for redundancy.
2. **Reflection Gate conditional repair routing** — three gates (seed_audit / tailor / final_review) now route `revise` verdicts back to upstream nodes via `route_after_gate(state, gate_name)`; `REFLECTION_GATE_MAX_ROUNDS=2` prevents infinite loops.
3. **Global Network Policy Guard** — `NetworkPolicyGuard` singleton intercepts all 9 retrieval adapters (arxiv/crossref/github/semantic_scholar/openalex/core/datacite/pubmed/huggingface); `network_policy=offline` fails fast with `NetworkPolicyViolation`.
4. **Three-Tier PASS standard** — `runtime_pass` / `contract_pass` / `quality_pass` reported independently with failure reasons.
5. **Fulltext Acquisition Layer** — `fulltext_acquisition_node` downloads PDFs via Unpaywall/arXiv, writes bytes to both `card["pdf_bytes"]` and `card["raw_input"]["pdf_bytes"]`.
6. **Decision Fusion** — `_compute_fused_verdict(state)` combines gate verdicts + novelty + gaps into `GO` / `CONDITIONAL` / `RISKY` / `BLOCKED`, persisted to `state.fused_verdict` (P0-A fix).
7. **Final Research Package** — `_assemble_final_research_package(state)` produces 7 sections: seed_audit_summary / tailor_summary / 3 gate_results / ledger / gap_status / hypothesis / fused_verdict.
8. **WP7 Frontend** — Seeded Research page + mode panel + result page with 7-section package export; static fixture 联调 passing.

## Post-audit fixes (this iteration)

After the P1 fixup round (commit a61a253d) reported `quality_pass=true` for yolo_steel/xlm_r while `fused_verdict=BLOCKED`, the audit identified two false-positive sources. Three commits resolved them:

- **commit c9ee3c62** — Removed `search_agent.py` P1-7b fallback (lines 1007-1025) that marked all open gaps as `partially_satisfied` whenever any papers/repos were found, regardless of attribution. Replaced with `plan_query_id` stable-propagation mechanism + `unassigned_evidence` tracking. Updated `_compute_quality_pass` to require (a) `fused_verdict != BLOCKED`, (b) no gate unresolved, (c) at least one gap with traceable `evidence_delta` in `search_steps`.
- **commit 73d97fab** — Fixed graph node order: `fulltext_acquisition → paper_understanding → method_family_explorer` (was reversed). PDF bytes now reach `paper_understanding` via `raw_input.pdf_bytes`.
- **commit e0239419** — Fixed `low_bar_review_node` crash when `work_package` LLM returns `data_source` / `experiment_metrics` as list instead of str. Added `_pkg_str()` helper.

## Final verification results

| Case | runtime | contract | quality | fused_verdict | elapsed |
|------|---------|----------|---------|---------------|---------|
| yolo_steel | ✅ true | ✅ true | ❌ false | BLOCKED | 579s |
| xlm_r | ✅ true | ✅ true | ❌ false | BLOCKED | 908s |
| vit_dr | ✅ true | ✅ true | ❌ false | BLOCKED | 849s |

**quality_pass=false is now trustworthy** — all three cases consistently report `BLOCKED + gate unresolved + low_bar inconsistent`, no longer self-contradicting with `quality_pass=true`.

**At least one gap with traceable evidence**: `gap-S1-competing_baseline` reaches `satisfied` in xlm_r/vit_dr (real attribution via `plan_query_id`). yolo_steel's gaps remain `open` because its search_steps' `gap_id` attribution didn't yield non-zero evidence_delta — this is honest reporting, not a regression.

## Remaining work (deferred to next iteration)

1. **Tailor Prompt / Schema tuning** — `tailored_method.core_method` empty across all three cases. Per spec.md "Recommendation: Tailor 上游输入完整性先于 Prompt 调优", diagnosis order is: (1) verify `fulltext_acquisition` actually downloaded PDF, (2) verify `paper_understanding` populated SeedCard fields, (3) verify `method_family_explorer` consumed them, (4) verify Tailor Adapter input prompt contains those fields, (5) only then tune Prompt/Schema/Gate.
2. **Seed Repair capability** — current seed_audit revise → seed_resolver loop may not add new capabilities (Crossref title search, author+year joint search, Semantic Scholar title resolution, user-confirmed candidate matching). Without these, ambiguous seeds stay ambiguous across rounds.
3. **Cross-domain expansion** — extend from 3 cases to 5-10 cross-domain seeded cases.
4. **WP7 real API integration** — current frontend uses static fixture; needs real backend API call-through.
5. **repair_cycles_detected metric accuracy** — `unresolved` (non-revise) currently not counted.

## SOP completion hook note

The `sop_completion_check.py` hook reports 17 unchecked items, but those items belong to the Re7.6 SOP file (`Plan/PaperAgent_Re7.6_真实链路阻塞修复与风险前瞻SOP.md`) — they are Re7.6 §2.4 testing requirements and §9.1 PASS conditions, not Re8.0 scope. The Re8.0 spec/tasks/checklist under `.trae/specs/re80-close-the-loop/` is fully closed.

## Commits in this iteration

- `a61a253d` — Re8.0 P1 fixup: gap_lookup miss fallback + gate cap routing + test coverage
- `317c38d0` — docs(re8.0): sync P1 fixup records to tasks.md + checklist.md
- `dac541fe` — Re8.0 WP1-WP6 production code: graph wiring + fulltext + network guard + adapters
- `d8d506dd` — Re8.0 tests: decision_fusion + fulltext + network_guard + pass_tiers
- `aa35c5a2` — Re8.0 WP7 frontend: Seeded Research page + UI primitives + fixture
- `490c8f2a` — Re8.0 artifacts: seeded demo results (3 cases) + final/ authoritative directory
- `dfbff286` — Re8.0 docs: spec + plan + AGENTS rule updates
- `c9ee3c62` — Re8.0 post-audit: fix quality_pass false positives + remove P1-7b fallback
- `73d97fab` — Re8.0 post-audit: fix fulltext/paper_understanding node order + field path
- `e0239419` — Re8.0 post-audit: fix low_bar_review crash when work_package fields are lists
- `f1bf43a2` — Re8.0 docs: sync post-audit fixes to spec/tasks/checklist

## Verdict

**Backend SOP scope: closed.**
The system now runs end-to-end on real seed papers without crash, reports contract fields correctly, and the `quality_pass` metric is trustworthy (no longer self-contradicting with `fused_verdict=BLOCKED`). The remaining `quality_pass=false` across all three cases reflects real upstream-input gaps (Tailor LLM output quality + Seed Repair capability) that are out of scope for this SOP and belong to the next iteration.

— ALLMIND, 2026-07-13
