# Re8.1 Research Quality Recovery Spec

## Why

Re8.0 原 SOP 已归档（backend closed），但 3/3 真实种子案例仍 `fused_verdict=BLOCKED`，`tailor_gate` 全部撞 cap (2/2)。第二/三次补丁（`8161ef6e` / `23867145` / `e2ddd8d7`）中第三次尚未重跑，且 `tailor_gate` 不收敛的真实根因（rule 兜底 vs LLM 主动拒绝 vs 上游缺失）从未诊断确认。Re8.1 需要从"工作流能跑通并诚实报告失败"升级到"让系统在真实种子论文上产生信息完整、可验证、可证伪的研究方法，并至少让部分标准案例达到非 BLOCKED 状态"。

## What Changes

- **WP0 版本冻结与单题 smoke**：在 `e2ddd8d7` 上跑 `vit_dr` 单题 smoke 验证第三次补丁效果，pass 则全量三题，fail 则作为权威基线进 WP1
- **WP1 Tailor Gate 收敛诊断与修复**：诊断优先——先查 `generated_by` 字段区分 rule 兜底 vs LLM 主动拒绝，再针对性修复；禁止盲目补字段或调 prompt
- **WP1-D Search Plan Lane 覆盖修复**：第三轮修复——`_seeded_plan()` 的 `queries[:12]` 截断导致后 3 个 lane(mechanism_module/resource/counter_evidence)查询被丢弃,fallback 无法触发;需引入 lane 公平分配(round-robin + MIN_PER_LANE)+ Phase 2 fallback 检查 evidence_gaps 中 open gap(不仅 search_plan 中 0 结果 gap)
- **WP2 Seed Repair 真实能力**：补标题相似度评分、年份冲突惩罚、候选置信度输出、冲突证据保留；20 个标题型种子验收
- **WP3 Tailor 输出质量门槛**：7 字段语义检查 + assembly_plan 结构（baseline/模块/连接/ablation≥4）+ 禁止泛化句
- **WP4 科研审查结果门槛**：至少 2/3 案例达 CONDITIONAL/RISKY/GO，至少 1/3 `quality_pass=true`；假阳性禁回归
- **WP5 真实前端链路**：前端调用真实后端 API（非 fixture），4 输入端到端，Gate 循环可见，错误状态诚实展示

## Impact

- **Affected specs**: Re8.0 WP6 (Reflection Gates)、Re8.0 P1-4 (Frontend)、Re8.0 spec.md "Recommendation: Tailor 上游输入完整性先于 Prompt 调优"
- **Affected code**:
  - `apps/api/scripts/re80_seeded_demo.py` — WP0 smoke + 诊断数据采集
  - `apps/api/app/services/agents/graph/nodes/reflection_gates.py` — WP1 诊断决策树 + 针对性修复
  - `apps/api/app/services/agents/graph/nodes/search_agent.py` — WP1 证据归因修复 + WP1-D Phase 2 fallback 兜底（检查 evidence_gaps 中 open gap）
  - `apps/api/app/services/agents/graph/nodes/search_planner.py` — WP1-D `_seeded_plan()` lane 公平分配修复（round-robin + MIN_PER_LANE）
  - `apps/api/app/services/agents/graph/nodes/tailor_skill_adapter.py` — WP1/WP3 上游链路 + 输出质量
  - `apps/api/app/services/agents/graph/nodes/seed_resolver.py` — WP2 Seed Repair 能力补全
  - `apps/api/app/services/agents/graph/nodes/content.py` — WP4 verdict 一致性
  - `apps/web-react/` — WP5 真实 API 集成
  - `artifacts/re8_0/final/` — WP0 权威基线 + WP4 最终验收
  - `artifacts/re8_1/` — 新增交接包目录

## ADDED Requirements

### Requirement: Third Batch Smoke Validation

WP0 SHALL 在 commit `e2ddd8d7` 上先运行 `vit_dr` 单题 smoke（最接近成功的案例，第二次重跑中已有 2/6 gap satisfied），根据 smoke 结果决定全量重跑或直接进 WP1 诊断。

#### Scenario: smoke 改善（fused_verdict != BLOCKED）
- **WHEN** vit_dr smoke 结果为 `fused_verdict != BLOCKED` 或 `tailor_gate` 未撞 cap
- **THEN** 全量重跑三案例，保存到 `artifacts/re8_0/final/`，更新 decision.md "Third Batch Iteration" 章节

#### Scenario: smoke 仍 BLOCKED
- **WHEN** vit_dr smoke 结果为 `fused_verdict=BLOCKED` 且 `tailor_gate` 仍撞 cap (2/2)
- **THEN** 记录为权威基线，采集 10 项诊断字段，进 WP1 诊断根因

#### Scenario: runtime/contract 回归
- **WHEN** smoke 出现 runtime 崩溃或 contract 字段回归
- **THEN** 立即回滚至 `23867145`，记录 regression，进 WP1

### Requirement: Diagnosis Data Collection

WP0 SHALL 无论 smoke pass/fail 都采集以下 10 项字段用于 WP1 诊断：`gate_results[].generated_by`、`gate_results[].rationale`、`gate_results[].round_idx`、`search_steps[].gap_id`、`search_steps[].plan_query_id`、`tailored_method.ablation_matrix` 长度、`tailored_method.core_method`、`tailored_method.assembly_plan.description`、`seed_cards[].raw_input.pdf_bytes`、`seed_cards[].task_definition` 等 5 字段。

#### Scenario: 诊断数据齐备
- **WHEN** WP0 完成
- **THEN** 10 项采集字段全部提取并保存，WP1 可直接基于该数据诊断

### Requirement: Diagnosis-First Root Cause Analysis

WP1 SHALL 在修复前先按诊断决策树确认 `tailor_gate` 不收敛的真实根因。决策树以 `gate_results[].generated_by` 为入口：`rule` → 检查 ablation_matrix 长度 / LLM trace / validator；`llm` → 检查 rationale 内容（evidence insufficient / core_method empty / ablation incomplete / 其他）。诊断输出 `diagnosis_report.json`，包含 `root_cause_category` / `evidence` / `recommended_fix_target` / `confidence`。

#### Scenario: rule 兜底触发
- **WHEN** `generated_by == "rule"` 且 ablation_matrix 长度 < 4
- **THEN** 根因诊断为 `rule_fallback`，修复目标为 Tailor LLM 输出（ablation 生成逻辑），不得降低 ablation 门槛

#### Scenario: LLM 主动拒绝（证据不足）
- **WHEN** `generated_by == "llm"` 且 rationale 提及 "evidence insufficient"
- **THEN** 根因诊断为 `evidence_attribution`，修复目标为 `plan_query_id` 端到端传播，不得重新引入 P1-7b fallback

#### Scenario: LLM 主动拒绝（上游缺失）
- **WHEN** `generated_by == "llm"` 且 rationale 提及 "core_method empty"
- **THEN** 根因诊断为 `upstream_missing`，按顺序验证 fulltext_acquisition → paper_understanding → method_family_explorer → tailor_skill_adapter

### Requirement: Targeted Fix Based on Diagnosis

WP1 SHALL 根据诊断结果针对性修复，不同根因对应不同修复目标。修复后重跑三案例验证至少 1/3 的 `tailor_gate` 在 2 轮内收敛。

#### Scenario: 修复后收敛
- **WHEN** WP1 修复后重跑，至少 1/3 案例的 `tailor_gate` 在 2 轮内 `verdict=pass` 或 `revise→pass`
- **THEN** WP1 通过，`fused_verdict` 不再因 tailor cap 而 BLOCKED

#### Scenario: 修复后仍不收敛
- **WHEN** 同一 failure signature 连续 3 次受控修改仍未改善
- **THEN** 触发硬停条件，停止 prompt 微调，提交 ADR，选择替换 provider / 降级能力 / 删除该节点

### Requirement: Search Plan Lane Coverage Guarantee

WP1-D SHALL 修复 `_seeded_plan()` 的 `queries[:12]` 截断问题,确保 5 个 lane(anchor_reference / competing_baseline / mechanism_module / resource / counter_evidence)每个至少有 `MIN_PER_LANE`(默认 2)个查询进入 search_plan。第二轮验证(commit `76686c32`)发现:前 2 个 lane 的查询数量已填满 12 个配额,后 3 个 lane 的查询被完全丢弃,导致这些 gap 既不在 search_plan 中,也无法触发 Phase 2 fallback,最终 0/3 案例 fallback 触发、0/3 案例 tailor_gate 收敛。

#### Scenario: 5 个 lane 均有查询覆盖
- **WHEN** `_seeded_plan` 从 5 个 lane 构建查询列表
- **THEN** search_plan 的 queries 列表中,每个 lane_id 至少出现 `MIN_PER_LANE`(2)次,后 3 个 lane(mechanism_module/resource/counter_evidence)不得被完全丢弃

#### Scenario: cap 仍保持 12
- **WHEN** 总查询数超过 12
- **THEN** 按 round-robin 从每个 lane 轮取查询,直到达到 cap=12;每个 lane 先保证 `MIN_PER_LANE` 个查询,剩余配额按 lane 顺序轮转分配

#### Scenario: Phase 2 fallback 覆盖未在 search_plan 中的 open gap
- **WHEN** Phase 2 fallback 执行时,`evidence_gaps` 中存在 status=open 且不在 search_plan 中的 gap
- **THEN** 该 gap 也进入 fallback 候选列表,`_build_fallback_query` 为其生成差异化查询(mechanism_module→arxiv method+ablation / resource→github method+object / counter_evidence→arxiv method+limitation+failure)

#### Scenario: fallback 真实触发
- **WHEN** WP1-D 修复后重跑三案例
- **THEN** 至少 2/3 案例的 search_steps 中出现 `fallback=True` 的步骤(对比第二轮 0/3 触发)

#### Scenario: 修复后收敛
- **WHEN** WP1-D 修复后重跑三案例
- **THEN** 至少 1/3 案例的 `tailor_gate` 在 2 轮内 `verdict=pass` 或 `revise→pass`(对比第二轮 0/3 收敛)

#### Scenario: 修复后仍不收敛
- **WHEN** 同一 failure signature(后 3 个 lane 0 查询覆盖 + fallback 0 触发)连续 3 次受控修改仍未改善
- **THEN** 触发硬停条件,提交 ADR,选择替换 provider / 降级能力 / 删除该节点

### Requirement: Title Similarity Scoring

WP2 SHALL 在 Seed Repair 候选排序中引入标题相似度评分（Levenshtein 或 token-based），与现有 DOI 优先 + 作者交集排序合并。

#### Scenario: 精确标题匹配
- **WHEN** 输入标题与候选标题完全一致
- **THEN** 相似度评分最高，候选排名靠前

#### Scenario: 轻微拼写错误
- **WHEN** 输入标题有 1-2 字符拼写错误
- **THEN** 相似度评分仍较高，候选可被选中

### Requirement: Year Conflict Penalty

WP2 SHALL 在候选年份与种子年份偏差 >2 年时对候选降权。

#### Scenario: 年份一致
- **WHEN** 候选年份与种子年份偏差 ≤2 年
- **THEN** 无降权

#### Scenario: 年份冲突
- **WHEN** 候选年份与种子年份偏差 >2 年
- **THEN** 候选降权，置信度降低

### Requirement: Candidate Confidence Output

WP2 SHALL 为每个候选输出 `confidence` 分数 + 排序依据（DOI 存在 / 作者交集 / 标题相似度 / 年份一致性）。

#### Scenario: 高置信候选
- **WHEN** 候选有 DOI + 作者完全匹配 + 标题相似度高 + 年份一致
- **THEN** `confidence=high`，排序依据记录所有命中项

#### Scenario: 低置信候选
- **WHEN** 候选无 DOI + 作者部分匹配 + 标题相似度中等
- **THEN** `confidence=low`，排序依据记录部分命中项

### Requirement: Conflict Evidence Preservation

WP2 SHALL 在 Crossref 与 Semantic Scholar 返回冲突候选时保留双源候选 + 标注冲突，不得静默丢弃任一来源。

#### Scenario: 双源一致
- **WHEN** Crossref 与 Semantic Scholar 返回相同候选
- **THEN** 合并为单一候选，标注双源一致

#### Scenario: 双源冲突
- **WHEN** Crossref 与 Semantic Scholar 返回不同候选
- **THEN** 保留双源候选，标注 `conflict=true`，由下游决策

### Requirement: Semantic Field Validation

WP3 SHALL 验证 Tailor 输出的 7 个字段（task_definition / method_summary / dataset_and_metrics / reproduction_environment / limitations / assembly_plan.description / core_method）不仅非空，且语义可追溯到种子论文内容。不得仅靠默认文本、标题扩写或泛化描述通过。

#### Scenario: 字段语义可信
- **WHEN** 字段非空且内容可追溯到论文
- **THEN** 字段验证通过

#### Scenario: 泛化句替代
- **WHEN** method_summary 为"添加注意力""加入多尺度模块"之类泛化句
- **THEN** 字段验证失败，标记为 `generic_substitute`

### Requirement: Assembly Plan Structure

WP3 SHALL 验证 `assembly_plan` 明确包含 baseline、模块列表（每个模块有名称+作用）、连接位置（模块如何接入 baseline）、至少 4 项 ablation、每个模块包含来源/输入输出语义/失败模式。

#### Scenario: 结构完整
- **WHEN** assembly_plan 包含 baseline + 模块 + 连接 + ablation≥4 + 模块详情
- **THEN** 结构验证通过

#### Scenario: ablation 不足
- **WHEN** ablation_matrix 长度 < 4
- **THEN** 结构验证失败

### Requirement: Real Backend API Integration

WP5 SHALL 让前端调用真实后端 API（非 fixture），支持 DOI / URL / title / PDF 四种输入，支持任务状态查询（异步轮询或 SSE），显示 Gate repair 循环（round_idx + verdict 变化），导出真实 Final Research Package（7 section）。

#### Scenario: DOI 输入端到端
- **WHEN** 用户在前端输入 DOI 并提交
- **THEN** 前端调用真实后端 API，异步查询任务状态，最终展示完整结果

#### Scenario: Gate 循环可见
- **WHEN** 后端 Gate 发生 repair 循环
- **THEN** 前端展示 round_idx 递增 + verdict 变化轨迹

### Requirement: Error State Honest Display

WP5 SHALL 在错误状态下诚实展示，不得伪装成成功页面。5 类场景：后端不可用、`fused_verdict=BLOCKED`、Gate unresolved、Seed ambiguous、网络离线模式。

#### Scenario: BLOCKED 不伪装
- **WHEN** 后端返回 `fused_verdict=BLOCKED`
- **THEN** 前端显示 BLOCKED + 原因，不得伪装为成功

#### Scenario: 后端不可用
- **WHEN** 后端 API 返回 5xx 或超时
- **THEN** 前端显示明确错误提示，不得显示空成功页

## MODIFIED Requirements

### Requirement: Tailor Gate Convergence (was: Re8.0 evaluation-only with cap)

Re8.0 中 `tailor_gate` 在 2 轮内未收敛则 emit `unresolved`，导致 `fused_verdict=BLOCKED`。Re8.1 修改为：通过 WP1 诊断优先路线，先确认根因再针对性修复，使至少 1/3 案例在 2 轮内收敛。`REFLECTION_GATE_MAX_ROUNDS=2` 保持固定，不得通过增加 cap 求收敛。

### Requirement: Seed Repair (was: Re8.0 commit 23867145 title-search)

Re8.0 第二次提交实现了 Crossref + Semantic Scholar 标题并行检索 + DOI 优先排序。Re8.1 修改为：补全标题相似度评分、年份冲突惩罚、候选置信度输出、冲突证据保留，并通过 20 个标题型种子验收。

### Requirement: Tailor Output (was: Re8.0 core_method tolerance)

Re8.0 第三次提交清理了 _TAILOR_PROMPT core_method 并加 description 兜底。Re8.1 修改为：不仅检查字段非空，还要验证语义可追溯性 + assembly_plan 结构完整性 + 禁止泛化句。

### Requirement: Quality Pass (was: Re8.0 post-audit false-positive fix)

Re8.0 post-audit 修复了 `quality_pass=true` + `fused_verdict=BLOCKED` 自相矛盾的假阳性。Re8.1 保持该硬性约束，并要求至少 1/3 案例真实达到 `quality_pass=true`（而非通过降低门槛）。

### Requirement: WP7 Frontend (was: Re8.0 static fixture)

Re8.0 WP7 只做静态 fixture 联调。Re8.1 修改为：前端调用真实后端 API，4 输入端到端，Gate 循环可见，错误状态诚实展示。

## REMOVED Requirements

### Requirement: Re8.0 Patch Accumulation
**Reason**: Re8.0 原 SOP 已归档，不再追加补丁。第二/三次补丁作为 Re8.1 WP0 的验证对象，后续修复全部纳入 Re8.1 范围。
**Migration**: Re8.0 decision.md 保持不变；Re8.1 完成后在同一 decision.md 新增 "Re8.1 Recovery Iteration" 章节。
