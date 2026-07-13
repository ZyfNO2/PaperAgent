# Re8.0 Close-the-Loop Spec

## Why

Re8.0 的后端节点骨架已搭好（WP0-WP6 主体实现存在，graph wiring 完成），但核心价值链没有真正闭环。3 道真实种子题的 demo 暴露了 4 个 P0 缺口和 4 个 P1 缺口：种子输入契约错误导致 6/6 种子未被核验、Reflection Gate 只评价不行动、PASS 标准过宽、Offline Replay 未严格断网。当前状态是"runtime pass 但 contract/quality 不 pass"，需要把 Reflection 和 Search 之间的行动闭环补上，让"核验 → 全文 → Tailor → 回搜 → 再审"真正跑通。

## What Changes

### P0 缺口（阻塞核心闭环）

- **P0-1 CandidateSeed 输入契约归一化**：Resolver 的 `_classify_input` 从 payload 顶层读 `doi/arxiv_id/url/title`，但 demo 把这些字段放在 `raw_input` 里。修两层：(a) 修 demo 按正式契约传顶层字段；(b) Resolver 增加输入归一化，兼容顶层和 `raw_input`，防止其他调用者再踩坑。
- **P0-2 Reflection Gate 闭环 (Conditional Repair Routing)**：当前 graph 全是静态 edge，Gate 返回 `revise` + `re_search_requests` 后仍继续向下执行。改为：seed_audit_gate `revise` → 回到 seed_resolver 或 repair 路径；tailor_gate `revise` → 回到 search_planner/search_agent；final_review_gate `revise` → 回到 evidence_context 或 innovation_extractor。引入 `REFLECTION_GATE_MAX_ROUNDS=2` 防死循环。
- **P0-3 Offline Replay 全局网络硬隔离**：当前只关闭 LLM/Seed 网络，Search Agent 仍可能调 Crossref/arXiv/GitHub Adapter。新增全局 Network Policy Guard：在 HTTP client/adapter 层安装拦截器，`network_policy=offline` 时任何 HTTP 调用立即失败。而非每个节点自己判断。
- **P0-4 PASS 标准分层**：当前 demo 只要 `final_recommendation` 非空就 PASS。拆成三层：(a) `runtime_pass` — pipeline 不 crash、final 非空；(b) `contract_pass` — Seed/Tailor/Gate/Ledger 字段正确完整；(c) `quality_pass` — 至少一个有效种子、方法非空、关键 Gap 已处理、最终 Verdict 与 Gate 一致。

### P1 缺口（影响真实可用性）

- **P1-1 DOI/arXiv 全文获取**：当前只拉元数据，`fulltext_status=metadata_only`，Paper Understanding 只读本地 PDF。新增 Fulltext Acquisition 层：DOI/arXiv → 落地页 → PDF/HTML 全文下载。区分 `metadata_verified` / `fulltext_available` / `fulltext_parsed` 三态。
- **P1-2 Decision Fusion**：当前 Final Recommendation 主要用旧字段（low_bar/human_gate/claim_judge），没有融合 Seed Gate/Tailor Gate/Final Review Gate。明确 Decision Fusion 规则：Seed Audit unresolved → 不能 GO；Tailor revise → 最高 CONDITIONAL；Novelty reject 但工程可行 → RISKY；存在关键未关闭 Gap → 不能生成强创新陈述。
- **P1-3 Final Research Package 组装**：当前最终对象只输出计数和 work package。组装真正的 Package：Seed Audit 结果、Tailor 方法图、3 个 Gate verdict + Ledger、Evidence Gap 状态、Falsifiable Hypothesis、最终 Verdict + rationale。
- **P1-4 WP7 前端扩展**：`apps/web-react` 已存在，不是独立项目。扩展 Seeded Research 流程：种子录入/PDF 上传/角色选择、模式开关、Seed 核验状态、Evidence Gap + 回搜原因、Tailor 方法图、Gate verdict + Ledger、Final Package 导出。**前置依赖**：P0-1/P0-2/P1-3 完成后才做前端联调。

### 不在本次 spec 范围

- WP7 前端的完整实现（先做静态 UI/fixture 联调，真实 API 联调等 P0 修完）
- `artifacts/re8_0` 交接包留档（最后一步，等闭环验证通过）

## Impact

- **Affected specs**: Re8.0 WP6 (Reflection Gates)、WP8 (Fixture/回归/演示)、Re7.7 Decision Calibration
- **Affected code**:
  - `apps/api/app/services/agents/graph/nodes/seed_resolver.py` — 输入归一化
  - `apps/api/app/services/agents/graph/research_graph.py` — conditional edges for repair routing
  - `apps/api/app/services/agents/graph/nodes/reflection_gates.py` — repair routing 协调
  - `apps/api/app/services/agents/graph/nodes/search_agent.py` — network policy guard
  - `apps/api/app/services/agents/graph/nodes/content.py` — decision fusion + final package
  - `apps/api/app/services/agents/graph/state.py` — 新增 fulltext_status / decision_fusion 字段
  - `apps/api/scripts/re80_seeded_demo.py` — 修输入契约 + PASS 分层
  - 新增 `apps/api/app/services/agents/graph/nodes/fulltext_acquisition.py`（P1-1）
  - 新增 `apps/api/app/services/network_guard.py`（P0-3）

## ADDED Requirements

### Requirement: CandidateSeed Input Normalization

Resolver SHALL accept candidate seeds in two forms: flat top-level fields (`doi`, `arxiv_id`, `url`, `title`, `pdf_path`) OR nested `raw_input` dict containing the same fields. `_classify_input` SHALL normalize both forms to a canonical flat payload before classification.

#### Scenario: Demo passes nested raw_input
- **WHEN** candidate seed has `raw_input: {"doi": "10.xxx", "title": "..."}` but no top-level `doi`
- **THEN** Resolver extracts `doi` from `raw_input` and proceeds with DOI verification

#### Scenario: Flat top-level fields (backward compat)
- **WHEN** candidate seed has top-level `doi: "10.xxx"`
- **THEN** Resolver uses it directly (existing behavior unchanged)

### Requirement: Reflection Gate Conditional Repair Routing

After a Reflection Gate returns `verdict=revise`, the graph SHALL route back to the appropriate upstream node instead of continuing forward. The routing target depends on the gate:
- `seed_audit_gate` revise → `seed_resolver` (re-resolve seeds with repair hints)
- `tailor_gate` revise → `search_planner` (targeted re-search based on `re_search_requests`)
- `final_review_gate` revise → `evidence_context` (compile more evidence)

Each gate caps at `REFLECTION_GATE_MAX_ROUNDS=2`. After the cap, gate emits `unresolved` and graph continues forward with a warning.

#### Scenario: seed_audit_gate returns revise
- **WHEN** seed_audit_gate returns `verdict=revise` with `re_search_requests=["S1"]` and round_idx < 2
- **THEN** graph routes back to `seed_resolver` with repair hints from the gate

#### Scenario: Gate cap reached
- **WHEN** gate round_idx == 2 and verdict is still `revise`
- **THEN** gate emits `unresolved`, graph continues forward, warning logged

### Requirement: Global Network Policy Guard

A single `NetworkPolicyGuard` SHALL intercept all outbound HTTP calls from search/ retrieval adapters when `network_policy=offline`. The guard wraps `httpx.Client`/`httpx.AsyncClient` at the adapter layer, raising `NetworkPolicyViolation` immediately on any call. Individual nodes do NOT need to check `network_policy` — the guard enforces it globally.

#### Scenario: Offline mode blocks arxiv adapter
- **WHEN** `network_policy=offline` and search_agent calls arxiv adapter
- **THEN** adapter raises `NetworkPolicyViolation` without making any HTTP request

#### Scenario: Full_agent mode allows all calls
- **WHEN** `network_policy=online` (default)
- **THEN** all adapters make HTTP calls normally (no interception)

### Requirement: Three-Tier PASS Standard

Demo/evaluation results SHALL report three separate pass/fail tiers:
- `runtime_pass`: pipeline completes without crash, `final_recommendation` is non-empty
- `contract_pass`: seed_cards, tailored_method, 3 gate_results, ledger all have expected fields populated
- `quality_pass`: ≥1 verified seed (seeded_research only), `tailored_method.core_method` (or `assembly_plan.description`) non-empty, ≥1 evidence gap with status `satisfied`/`partially_satisfied` AND a traceable `evidence_delta` in `search_steps` (gap_id must appear in ≥1 step with non-zero papers/repos), `fused_verdict != BLOCKED`, no Reflection Gate (seed_audit / tailor / final_review) is `unresolved`, `final_recommendation.low_bar_status == "pass"`, and (if present) `novelty_review_verdict != "reject"`. Re8.0 post-audit: the BLOCKED / unresolved / no-traceable-evidence guards were added because the previous definition reported `quality_pass=true` even when `fused_verdict=BLOCKED`, creating a self-contradictory result.

#### Scenario: All seeds ambiguous
- **WHEN** 6/6 seeds are `ambiguous` and 3 gates return `revise`
- **THEN** `runtime_pass=true`, `contract_pass=false` (seed_cards missing resolved_title), `quality_pass=false`

### Requirement: Fulltext Acquisition Layer

A new `fulltext_acquisition_node` SHALL download PDF/HTML fulltext for verified seed papers (DOI → publisher landing page → PDF URL → download). Seeds progress through three states: `metadata_verified` → `fulltext_available` → `fulltext_parsed`.

#### Scenario: DOI seed gets fulltext
- **WHEN** seed has `existence_status=verified` and `fulltext_status=metadata_only`
- **THEN** fulltext_acquisition_node downloads PDF and sets `fulltext_status=fulltext_available`

#### Scenario: Paywalled paper
- **WHEN** PDF download fails (403/paywall)
- **THEN** `fulltext_status` stays `metadata_only`, gap opened with type=`fulltext`

### Requirement: Decision Fusion

Final Recommendation SHALL compute `fused_verdict` by combining all upstream signals:
- Seed Audit `unresolved` → `fused_verdict=BLOCKED`
- Tailor `revise` → cap `fused_verdict` at `CONDITIONAL`
- Novelty `reject` + Tailor `GO` → `fused_verdict=RISKY`
- Any critical evidence gap open → `fused_verdict` cannot be `GO`
- All gates `pass` + novelty `accepted` + gaps closed → `fused_verdict=GO`

#### Scenario: Gates revise but low_bar pass
- **WHEN** 3 gates return `revise` but `low_bar_status=pass`
- **THEN** `fused_verdict=CONDITIONAL` (not `GO`)

### Requirement: Final Research Package

Final state SHALL include `final_research_package` dict containing: seed_audit_summary, tailor_summary, 3 gate_results, ledger_entries, evidence_gap_status, falsifiable_hypothesis, fused_verdict + rationale.

#### Scenario: Package assembled
- **WHEN** pipeline completes
- **THEN** `final_research_package` contains all 7 sections with non-empty values

## MODIFIED Requirements

### Requirement: Reflection Gate Semantics (was: evaluation-only)

Previously gates only evaluated and emitted `re_search_requests` as audit trail. Now gates actively trigger repair routing via conditional edges. The `re_search_requests` field is consumed by the graph router, not just logged.

### Requirement: PASS Criteria (was: single binary)

Previously demo reported single PASS/FAIL. Now reports `runtime_pass` / `contract_pass` / `quality_pass` as three independent booleans.

### Requirement: Fulltext Acquisition Before Paper Understanding (post-audit)

Originally the graph ordered `paper_understanding → fulltext_acquisition → method_family_explorer`. This caused `paper_understanding` to run on a seed card with only metadata — the PDF had not yet been downloaded. `fulltext_acquisition` then downloaded the PDF, but the graph did not return to `paper_understanding`, so the freshly downloaded PDF was never parsed.

**Fix (commit 73d97fab)**: graph order is now `fulltext_acquisition → paper_understanding → method_family_explorer`. `fulltext_acquisition_node` writes downloaded PDF bytes to BOTH `card["pdf_bytes"]` AND `card["raw_input"]["pdf_bytes"]` — the latter is the path `paper_understanding` actually reads. `seed_audit_gate`'s forward target was updated from `paper_understanding` to `fulltext_acquisition` accordingly.

#### Scenario: DOI seed gets fulltext parsed
- **WHEN** seed has `existence_status=verified` and `fulltext_status=metadata_only`
- **THEN** `fulltext_acquisition_node` downloads PDF → `paper_understanding` parses `raw_input.pdf_bytes` → `method_family_explorer` consumes the parsed SeedCard fields (task_definition / method_summary / dataset / environment)

### Requirement: Evidence Gap Attribution Stability (post-audit, was P1-7b fallback)

Previously `search_agent.py` had a fallback (P1-7b, commit a61a253d) that marked ALL open gaps as `partially_satisfied` whenever the ReAct LLM reformulated a query such that `(tool, query)` no longer matched the `gap_lookup`, but search still returned any papers/repos. This produced `gap_id=null` / `evidence_delta=null` in `search_steps`, proving only "search had results" — not that any specific Gap was actually addressed.

**Fix (commit c9ee3c62)**: the P1-7b fallback is removed. In its place:
1. `_build_gap_lookup` returns `(by_tool_query, by_query_id)` tuple; each gap_meta carries a deterministic `query_id` (`q_{gap_id}_{n}`).
2. The system prompt exposes structured `plan_queries` (query_id + gap_id + query_text + tool) and instructs the LLM to echo `plan_query_id` when reformulating.
3. The ReAct loop uses `_resolve_gap_meta(tool, query, plan_query_id)` — `plan_query_id` lookup first, then `(tool, query)` fallback — to keep `gap_id` stable across reformulation.
4. Search results that cannot be attributed to any gap (gap_lookup miss + no `plan_query_id`) go into `unassigned_evidence` (for traceability only), NOT into marking any gap as `partially_satisfied`.

A gap may only be marked `partially_satisfied` when (a) the search action was bound to a `gap_id`, (b) ≥1 result passed relevance check, (c) the result produced a recordable Evidence ID, and (d) the Gap's success condition is partially met.

#### Scenario: LLM reformulates query but plan_query_id preserved
- **WHEN** LLM rewrites `query_text` but echoes `plan_query_id="q_gap-S1-task_definition_for_family_1"`
- **THEN** the search result is attributed to `gap_id="gap-S1-task_definition_for_family"` and may update that gap's status

#### Scenario: LLM drops plan_query_id
- **WHEN** LLM returns a reformulated query without `plan_query_id` and `(tool, query)` does not match any entry in `gap_lookup`
- **THEN** search results go into `unassigned_evidence`; no gap is marked `partially_satisfied`

### Recommendation: Tailor 上游输入完整性先于 Prompt 调优

Post-audit 第二轮重跑确认 xlm_r/vit_dr 的 `tailored_method.core_method` 仍为空，`tailor_gate` round_idx 达到 cap，`fused_verdict=BLOCKED`。但这**不是 Tailor Prompt 单点问题** — Tailor 的上游输入链路仍可能不完整：

1. `fulltext_acquisition` 是否真的下载到了 PDF（DOI/arXiv 种子可能因 Unpaywall 无 OA 副本而失败）
2. `paper_understanding` 是否消费了下载的 PDF 并填充了 SeedCard 的 `task_definition` / `method_summary` / `dataset` / `environment` 字段
3. `method_family_explorer` 是否消费了上述 SeedCard 字段
4. `tailor_skill_adapter` 的输入 prompt 是否包含 `task_definition` / `method_summary` / `dataset` / `environment`

**推荐诊断顺序**（必须在 Tailor Prompt 调优之前）：
1. 检查下载后的 PDF 是否真的进入 `paper_understanding`（查 trace_events + `card["raw_input"]["pdf_bytes"]` 非空）
2. 检查 SeedCard 的 `task_definition`/`method_summary`/`dataset`/`environment` 是否被填充
3. 检查 `MethodFamily` 是否消费这些字段
4. 检查 Tailor Adapter 输入 prompt 是否包含这些字段
5. 最后才调 Prompt / Schema / Gate 判定

在 (1)-(4) 任何一步缺失的情况下，单纯调 Tailor Prompt 只会让 LLM 在缺失输入上"编造" core_method，产生新的假阳性。

## REMOVED Requirements

### Requirement: WP7 as out-of-scope
**Reason**: `apps/web-react` already exists with Home/Workbench/Settings. WP7 is extending existing frontend, not a new project.
**Migration**: P1-4 task covers frontend extension, but deferred until P0 backend fixes complete.
