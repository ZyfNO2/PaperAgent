# Re8.2 SeedAudit收敛·Gate路由修复与真实E2E SOP Spec

## Why
Re8.1 已证明 Tailor LLM 可以在两轮内返回 `pass`。当前长期阻塞来自两个工程问题：(1) `final_review_gate` repair 后重复进入已通过的 `tailor_gate`，旧 round 被继续累计，最终 cap → `unresolved`；(2) `xlm_r S1` 与 `yolo_steel S2` 需要 Seed Repair 2.0，基础标题匹配不足以处理标题别名、作者年份冲突和无稳定 identifier 的情况。

WP1 已修复 Gate 重入问题。WP2-WP6 需依次完成以将整个 SOP 推进到最终验证状态。

## What Changes

### WP2 — Seed Repair 2.0
- 新增 `SeedCandidate` 统一模型（Crossref/Semantic Scholar/OpenAlex/arXiv 归一化）
- 新增 `_fetch_seed_candidates` 并行多源检索（完整标题、去副标题、作者+核心词、年份+核心词）
- 实现结构化评分（title 0.35 + author 0.25 + year 0.15 + abstract 0.15 + identifier 0.10）
- 实现 LLM 消歧（仅在 2-5 候选且分差 <0.08 时调用，不能创造候选）
- false verification rate 必须为 0

### WP3 — Seed Audit Gate 结构化 reason code
- 新增 reason codes: SEED_NOT_FOUND / SEED_LOW_CONFIDENCE / SEED_SOURCE_CONFLICT / SEED_AUTHOR_MISMATCH / SEED_YEAR_MISMATCH / SEED_IDENTIFIER_CONFLICT / SEED_FULLTEXT_UNAVAILABLE / SEED_VERIFIED
- `seed_audit_gate` 输出必须包含 `reason_code`, `seed_id`, `candidate_count`, `top_score`, `repair_target`
- 保持现有 verdict 兼容；新增字段必须 additive

### WP4 — 真实三案例重跑
- 顺序：vit_dr → xlm_r → yolo_steel
- 每案例保存完整 trace、seed_candidates、gate_cycles、final_package、metrics
- 验收：至少 2/3 非 BLOCKED，至少 1/3 `quality_pass=true`，vit_dr 不得因 Tailor 重入 blocked

### WP5 — 真实前后端 E2E
- Playwright 不得使用 `page.route()` mock
- 启动真实 API + 前端 dev server，输入稳定 DOI，轮询直到完成
- 验证状态轮询、Gate rounds、final package 下载及 JSON 一致性

### WP6 — 标准交接包
- 输出到 `artifacts/re8_2/final/` — manifest.json, metrics.json, decision.md, regression_report.json, e2e_report.json, known_gaps.json
- `decision.md` 区分 verified/inferred/proposed/unknown
- 最终状态 PASS / PARTIAL / NO-GO

## Impact
- Affected code: `seed_resolver.py`, `reflection_gates.py`, `re80_schema.py`, `research_graph.py`
- New files: `SeedCandidate` model embedded in `re80_schema.py`, seed audit fixture, `test_re8_2_seed_repair.py`, `test_re82_seeded_e2e.py`, `scripts/re82_wp*.py`
- Affected tests: `test_re8_seed_resolver.py`, `test_re8_reflection_gates.py`, 新 `test_re8_seed_repair.py`
- Affected artifacts: `artifacts/re8_2/`

## ADDED Requirements

### Requirement: SeedCandidate 统一模型
系统 SHALL 定义 `SeedCandidate(TypedDict)` 统一所有数据源（Crossref/S2/OpenAlex/arXiv）的候选结构。

#### Scenario: 单源解析
- **WHEN** 从 Crossref 获取一条候选
- **THEN** 归一化为 SeedCandidate：title, authors, year, doi, arxiv_id, canonical_url, abstract, venue, sources, 各种 score, total_score, confidence, conflicts

#### Scenario: 多源合并
- **WHEN** 多个来源返回同一论文（DOI 匹配或标题高度相似）
- **THEN** 合并为一个 SeedCandidate，sources 列表记录所有来源

### Requirement: 并行多策略检索
系统 SHALL 支持四种查询策略并行执行：完整标题、去副标题标题、第一作者姓氏+核心标题词、年份+核心标题词。

#### Scenario: 四种策略并行
- **WHEN** `_fetch_seed_candidates` 被调用
- **THEN** 四条查询并行到 all available sources，结果归一化到 SeedCandidate

#### Scenario: 标题归一化
- **WHEN** 标题包含冒号副标题、Unicode 差异或大小写差异
- **THEN** 归一化后忽略此类差异进行匹配

### Requirement: 结构化评分与阈值
系统 SHALL 使用加权评分公式 `total = 0.35*title + 0.25*author + 0.15*year + 0.15*abstract + 0.10*identifier`。

#### Scenario: 高置信度验证
- **WHEN** `total >= 0.85` 且无关键冲突
- **THEN** 返回 `verified`

#### Scenario: 模糊需要消歧
- **WHEN** `0.70 <= total < 0.85`
- **THEN** 返回 `ambiguous` 或进入 LLM 消歧

#### Scenario: 低置信度拒绝
- **WHEN** `total < 0.70`
- **THEN** 返回 `not_found` 或 `ambiguous`

### Requirement: LLM 受限消歧
系统 SHALL 仅在 2-5 个候选、top1-top2 分差 <0.08、至少一项得分 >=0.70 时调用 LLM 消歧。

#### Scenario: LLM 选择候选
- **WHEN** LLM 被调用且 `reject_all=false`
- **THEN** `selected_index` 指向已有候选之一，`confidence` 为 high/medium/low

#### Scenario: LLM 拒绝所有
- **WHEN** LLM 返回 `reject_all=true` 或 `confidence=low`
- **THEN** 不得 verified，seed 保持 ambiguous

### Requirement: Seed Audit Gate 结构化 reason code
系统 SHALL 在 `seed_audit_gate` 输出中包含结构化 `reason_code` 字段。

#### Scenario: revise 输出
- **WHEN** seed 被判定为需 revise
- **THEN** 输出包含 `{"verdict": "revise", "reason_code": "SEED_LOW_CONFIDENCE", "seed_id": "S2", "candidate_count": 3, "top_score": 0.78, "repair_target": "seed_resolver"}`

#### Scenario: pass 输出
- **WHEN** seed 被判定为 pass
- **THEN** 输出包含 `{"verdict": "pass", "reason_code": "SEED_VERIFIED", "seed_id": "S1"}`

### Requirement: 真实前后端 E2E
系统 SHALL 使用 Playwright 对真实 API+前端进行 E2E 验证，禁止 mock。

#### Scenario: 提交 DOI 任务
- **WHEN** 输入 `10.18653/v1/N19-1423` 创建任务
- **THEN** 启动真实 API，任务状态轮询正常，最终可下载 final package

#### Scenario: Gate 状态展示
- **WHEN** 任务完成后查看前端
- **THEN** Seed / Gate cycle / repair / fused verdict 在前端正确显示

### Requirement: 标准交接包
系统 SHALL 在 `artifacts/re8_2/final/` 下生成标准命名和结构的交接包。

#### Scenario: decision.md 区分可信等级
- **WHEN** decision.md 被生成
- **THEN** 每个结论标记 verified / inferred / proposed / unknown

## MODIFIED Requirements
无。WP2-WP6 全部为新增。

## REMOVED Requirements
无。
