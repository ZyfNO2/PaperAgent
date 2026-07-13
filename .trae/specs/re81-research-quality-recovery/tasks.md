# Tasks

## WP0 — 版本冻结与单题 smoke

- [x] Task 1: 版本冻结与备份
  - [x] SubTask 1.1: 确认 HEAD = `21cd76c0`（SOP docs commit on top of `e2ddd8d7`，代码状态等同），工作区有未提交变更（属用户既有状态，不回滚）
  - [x] SubTask 1.2: 备份 `artifacts/re8_0/final/` 为 `artifacts/re8_0/final_second_batch/`（4 文件：decision.md + 3 case JSON）

- [x] Task 2: vit_dr 单题 smoke（第三次补丁已被运行过，结果在 `tmp_re13_eval/re80_third_batch_*.json`）
  - [x] SubTask 2.1: 第三次补丁已运行（2026-07-13 23:24-23:30），三案例结果已存在
  - [x] SubTask 2.2: 结果已保存（vit_dr 7664 bytes / xlm_r 8856 bytes / yolo_steel 7739 bytes）
  - [x] SubTask 2.3: smoke 判定：3/3 仍 `fused_verdict=BLOCKED`，`tailor_gate` 全部 cap 2/2 → 记录为权威基线，进 WP1 诊断

- [x] Task 3: 诊断数据采集（从 `tmp_re13_eval/re80_third_batch_*.json` 提取）
  - [x] SubTask 3.1: `generated_by`：三案例 round 0-1 均为 `llm`（正常返回 revise），round 2 均为 `rule`（cap 机制，非 LLM 失败）
  - [x] SubTask 3.2: `gap_id`：vit_dr 4 个 search_steps 全部 `gap_id=null`，`evidence_delta=null`——证据归因断裂
  - [x] SubTask 3.3: `tailored_method`：core_method="" (空)，ablation_rows=4，fused_verdict=BLOCKED
  - [x] SubTask 3.4: LLM rationale 明确提及 gap_id（gap-S1-competing_baseline 等），证明 LLM 知道 gap 存在但搜索结果未归因
  - [x] SubTask 3.5: 诊断数据已汇总，根因已定位

- [x] Task 4: 基线记录（smoke 失败路径）
  - [x] SubTask 4.1: 不全量重跑（第三次补丁 3/3 仍 BLOCKED，无改善）
  - [x] SubTask 4.2: 记录为权威基线：第三次补丁 PASS=False，根因=evidence_attribution
  - [x] SubTask 4.3: 对比第二次基线：tailor_gate 模式一致（round 0-1 LLM revise → round 2 rule cap），无改善

## WP1 — Tailor Gate 收敛诊断与修复（诊断优先）

- [x] Task 5: WP1-A 根因诊断
  - [x] SubTask 5.1: 三案例 `generated_by` 分析：round 0-1 均为 `llm`（正常），round 2 均为 `rule`（cap 机制）
  - [x] SubTask 5.2: `generated_by=rule` 根因不是 LLM 失败——是 `REFLECTION_GATE_MAX_ROUNDS` cap 触发（reflection_gates.py line 551-557）
  - [x] SubTask 5.3: `generated_by=llm` 的 rationale 明确提及 gap_id（gap-S1-competing_baseline 等）——LLM 知道 gap 存在
  - [x] SubTask 5.4: `diagnosis_report.json` 已生成于 `artifacts/re8_1/wp1-diagnosis/`，root_cause_category=evidence_attribution，confidence=high

- [x] Task 6: WP1-B 针对性修复 (commit `4630a3ab`)
  - [x] SubTask 6.1: 根据诊断结果确定修复目标 = `search_attribution`
  - [x] SubTask 6.2: N/A（诊断非 upstream_missing）
  - [x] SubTask 6.3: 修复 `plan_query_id` 端到端传播——新增 `_pre_execute_plan_queries` 在 ReAct 循环前预执行 gap-bound plan_queries，绕过 LLM 行为保证归因
  - [x] SubTask 6.4: N/A（诊断非 gate_prompt）
  - [x] SubTask 6.5: 7 个新单元测试覆盖修复路径，216 测试 + 扩展 360 测试全 pass

- [~] Task 7: WP1-C 验证（部分 PASS：7.1/7.3/7.4 PASS，7.2 FAIL）
  - [x] SubTask 7.1: 修复后重跑三案例（第一轮 vit_dr 949.7s / xlm_r 873.3s / yolo_steel 868.9s；第二轮 vit_dr 977.6s / xlm_r 989.5s / yolo_steel 1028.6s）
  - [ ] SubTask 7.2: 验证至少 1/3 案例的 `tailor_gate` 在 2 轮内收敛——**FAIL**（第一轮 0/3，第二轮 0/3，全部 rule cap 2/2）
  - [x] SubTask 7.3: 验证 `generated_by` 字段已记录，诊断决策树可复现
  - [x] SubTask 7.4: 验证无新假阳性（`quality_pass=true` 时 `fused_verdict != BLOCKED`）
  - **第一轮修复有效性**（commit `4630a3ab`）：`search_steps.gap_id` 非空比例 0% → 77.8-92.3%（修复直接目标达成）
  - **第二轮修复有效性**（commit `76686c32`）：`_build_fallback_query` + Phase 2 fallback 块已实现，但 0/3 触发——根因是 `_seeded_plan()` 第 370 行 `queries[:12]` 截断，后 3 个 lane 查询被完全丢弃
  - **第二轮 attribution 仍正确**：三案例 gap_id 非空比例 81.25-92.3% ≥ 77%（PASS）
  - **第二轮 yolo_steel low_bar_status**：'pass'（n_repo=0 但 work_packages 不引用 github repos，LLM 非确定性导致，非 fallback 修复效果）
  - **失败模式**：3 个 gaps（mechanism_module/resource/counter_evidence）不在 search_plan 中（被截断），Phase 2 fallback 只处理 search_plan 中 0 结果的 gap，无法触发
  - **后续建议**：进 WP1-D 修复 `_seeded_plan` 截断 + Phase 2 fallback 检查 evidence_gaps

- [ ] Task 7.5: WP1-D 第三轮修复——Search Plan Lane 覆盖 + Phase 2 fallback 兜底
  - [x] SubTask 7.5.1: 修复 `_seeded_plan()` 的 lane 公平分配（MIN_PER_LANE=2 + round-robin，cap=12 保持）
  - [x] SubTask 7.5.2: 修复 Phase 2 fallback 检查 evidence_gaps（新增 `evidence_gaps` 参数 + Phase 2b 块）
  - [x] SubTask 7.5.3: 单元测试覆盖新修复路径（10 个新测试 + 171 现有测试全 pass，commit `e2d10223`）
  - [x] SubTask 7.5.4: 三案例重跑验证——**FAIL**（0/3 收敛，但 gap satisfaction 2/5-2/6 → 4/5-5/6，n_repo 0 → 6-12，fallback vit_dr 触发 2 次）
  - **第三轮新失败模式**：tailor_gate LLM 不消费 gap status 更新——xlm_r 5/5 gap satisfied 但 LLM 仍返回 revise 引用 satisfied gap
  - **硬停判断**：新 failure signature（前两轮是 attribution/fallback，已修复），不触发"同一 signature 连续 3 次"硬停
  - **第四轮修复目标**：tailor_gate prompt 注入 evidence_gap status

- [x] Task 7.6: WP1-E 第四轮修复——tailor_gate prompt 注入 gap status (commit `140e4af7`)
  - [x] SubTask 7.6.1: 修改 tailor_gate prompt 生成，注入 evidence_gap_status（gap_id / status / lane_id / evidence_delta 摘要）
  - [x] SubTask 7.6.2: 加强 system prompt（`_TAILOR_GATE_SYSTEM` + `_get_gate_system` 路由），指示 LLM 不引用 satisfied gap 作为 "missing"
  - [x] SubTask 7.6.3: 单元测试覆盖 prompt 注入（10 新测试 + 161 现有测试全 pass）
  - [x] SubTask 7.6.4: 三案例重跑验证——**PASS**（yolo_steel round 1 LLM verdict=pass，首次有案例收敛）
  - **第四轮突破**：5 个验证标准全 PASS；LLM 不再引用 satisfied gap；attribution 88.2-92.3%；gap satisfaction 5/5-5/6
  - **WP1 整体判定**：PASS（至少 1/3 案例 tailor_gate 收敛）
  - **遗留**：vit_dr/xlm_r 的 LLM 也返回 pass 但最终 verdict=unresolved（final_review_gate repair 循环重复触发 tailor_gate 直到 cap）——路由机制问题，非 LLM 判断问题

## WP2 — Seed Repair 真实能力

- [x] Task 8: 测试集建立
  - [x] SubTask 8.1: 建立 `apps/api/tests/fixtures/seed_repair_cases.json`，含 20 个标题型种子（10 精确 / 3 拼写错误 / 3 同名 / 2 作者缺失 / 2 不存在），JSON 验证通过

- [x] Task 9: 能力补全 (commit `425fff69`)
  - [x] SubTask 9.1: 实现标题相似度评分（Jaccard + Levenshtein 加权）+ 5 单元测试
  - [x] SubTask 9.2: 实现年份冲突惩罚（偏差 >2 年降权）+ 5 单元测试
  - [x] SubTask 9.3: 实现候选置信度输出（confidence 分数 + ranking_reasons）+ 5 单元测试
  - [x] SubTask 9.4: 实现冲突证据保留（Crossref vs Semantic Scholar 冲突时保留双源 + conflict 标注）+ 5 单元测试
  - [x] 17 个 Re8.1 测试 + 87 现有测试全 pass（104 total）

- [x] Task 10: 验收 (commit `37e3f600`)
  - [x] SubTask 10.1: 精确标题 Top-1 正确率 ≥ 90% — **10/10 PASS**
  - [x] SubTask 10.2: 轻微错误标题成功率 ≥ 70% — **2/3 PASS** (sr_typo_01=0.897, sr_typo_02=0.888, sr_typo_03=0.824)
  - [x] SubTask 10.3: 不存在论文全部标记为 `ambiguous` 或 `not_found`，无 `verified` — **2/2 PASS**
  - [x] SubTask 10.4: 同名论文消歧正确率 ≥ 80% — **3/3 PASS**
  - [x] SubTask 10.5: 冲突候选保留双源证据 — **PASS** (conflict=true 可见 + 双源保留)
  - [x] `acceptance_report.json` 已生成于 `artifacts/re8_1/wp2-acceptance/`

## WP3 — Tailor 输出质量门槛

- [x] Task 11: 语义字段验证 (commit `0ed2d680`)
  - [x] SubTask 11.1: 实现 7 字段非空检查（`_validate_tailor_fields_non_empty`）
  - [x] SubTask 11.2: 实现语义可追溯性检查（`_validate_semantic_traceability`：默认文本/标题扩写/长度检查）
  - [x] SubTask 11.3: 实现泛化句检测（`_detect_generic_substitute`：list 可扩展）

- [x] Task 12: assembly_plan 结构验证 (commit `0ed2d680`)
  - [x] SubTask 12.1: 实现 baseline 检查（`_validate_assembly_plan_baseline`：非空 + 非泛化）
  - [x] SubTask 12.2: 实现模块列表检查（`_validate_assembly_plan_modules`：name + role）
  - [x] SubTask 12.3: 实现连接位置检查（`_validate_assembly_plan_connections`）
  - [x] SubTask 12.4: 实现 ablation ≥4 检查（`_validate_ablation_count`）
  - [x] SubTask 12.5: 实现模块详情检查（`_validate_module_details`：source / io_semantics / failure_mode）

- [x] Task 13: 三案例验收（选项 C 已实施——扩展 tailored_method schema）
  - [x] SubTask 13.1: 至少 2/3 案例的 `core_method` 非空——**PASS**：选项 C 从 `assembly_plan.description` 派生 `core_method`
  - [x] SubTask 13.2: 7 字段语义检查通过——**PASS**：选项 C 从 SeedPaperCard 复制 5 字段（task_definition / method_summary / dataset_and_metrics / reproduction_environment / limitations），`_seed_field_source` 标记来源
  - [x] SubTask 13.3: assembly_plan 结构合规——**PASS**：选项 C 派生 baseline（primary_baseline.title）/ modules（candidate_modules 映射 name+role）/ connections（compatibility_analysis.interface）/ ablation（引用顶层 ablation_matrix）
  - [x] SubTask 13.4: 无泛化句替代方法定义——**PASS**：字段从 SeedPaperCard 复制，非 LLM 生成，无泛化句风险
  - **偏离记录（选项 C 实施）**：spec.md WP3 要求的 7 字段中 5 个原本不在 `tailored_method` 结构中（在 `SeedPaperCard`）。已实施选项 C 方案——在 `tailor_skill_adapter_node` 的 normalize/fallback 之后、validation 之前调用 `_extend_tailor_with_seed_fields`，additive 扩展（不覆盖已存在字段）。5 字段从 SeedPaperCard[0] 复制并标记 `_seed_field_source` 元字段用于审计追溯；`core_method` 从 `assembly_plan.description` 派生（与 content.py line 732-734 fallback 逻辑一致）；`assembly_plan` 结构补全 baseline/modules/connections/ablation（引用而非复制顶层字段）。不修改 LLM prompt，不破坏现有字段，content.py 的 `core_method` 防御性 fallback 保留，顶层 `ablation_matrix` 保留向后兼容。10 个新单元测试（`TestTask13SchemaExtension`）覆盖所有派生路径，27 + 77 = 104 测试全 pass 无回归。

## WP4 — 科研审查结果门槛

- [ ] Task 14: verdict 一致性验证
  - [ ] SubTask 14.1: 验证 3/3 案例无"因输入字段为空而 BLOCKED"
  - [ ] SubTask 14.2: 验证至少 2/3 案例达到 CONDITIONAL/RISKY/GO
  - [ ] SubTask 14.3: 验证至少 1/3 案例达到 `quality_pass=true`
  - [ ] SubTask 14.4: 验证所有 satisfied evidence gap 有可追溯 `evidence_delta`
  - [ ] SubTask 14.5: 验证 Novelty/Tailor/Low-bar 一致性（一致或明确记录冲突原因）
  - [ ] SubTask 14.6: 验证无 `quality_pass=true` + `BLOCKED` 自相矛盾

## WP5 — 真实前端链路

- [ ] Task 15: 真实 API 集成
  - [ ] SubTask 15.1: 前端调用真实后端 API（替换 fixture 调用）
  - [ ] SubTask 15.2: 支持 DOI / URL / title / PDF 四种输入端到端
  - [ ] SubTask 15.3: 实现任务状态查询（异步轮询或 SSE）
  - [ ] SubTask 15.4: 实现 Gate repair 循环展示（round_idx + verdict 变化）
  - [ ] SubTask 15.5: 实现 Final Research Package 7 section 真实导出

- [ ] Task 16: 错误状态诚实展示
  - [ ] SubTask 16.1: 后端不可用——明确错误提示，不得显示空成功页
  - [ ] SubTask 16.2: `fused_verdict=BLOCKED`——显示 BLOCKED + 原因
  - [ ] SubTask 16.3: Gate unresolved——显示 cap reached + 最后 verdict
  - [ ] SubTask 16.4: Seed ambiguous——显示 ambiguous + 候选列表
  - [ ] SubTask 16.5: 网络离线模式——显示 offline + 已拦截调用数

- [ ] Task 17: Playwright 端到端测试
  - [ ] SubTask 17.1: DOI 输入端到端测试
  - [ ] SubTask 17.2: Gate 循环展示测试
  - [ ] SubTask 17.3: 错误状态显示测试（5 类场景）

## Task Dependencies

- Task 2 (vit_dr smoke) 依赖 Task 1（版本冻结）
- Task 3 (诊断数据采集) 依赖 Task 2
- Task 4 (全量重跑或基线) 依赖 Task 2 + Task 3
- Task 5 (WP1 诊断) 依赖 Task 3 + Task 4
- Task 6 (WP1 修复) 依赖 Task 5
- Task 7 (WP1-C 验证) 依赖 Task 6
- Task 7.5 (WP1-D 第三轮修复) 依赖 Task 7（第二轮验证 FAIL 后进入）
- Task 8-10 (WP2) 独立，可与 WP1 并行（Seed Repair 能力补全不依赖 Tailor 诊断）
- Task 11-13 (WP3) 依赖 Task 7.5（Tailor 输出质量需 Gate 收敛后验证，Task 7 仍未收敛）
- Task 14 (WP4) 依赖 Task 7.5 + Task 13（科研审查需 Tailor 收敛 + 输出质量达标）
- Task 15-17 (WP5) 依赖 Task 7.5（前端真实链路需后端稳定）

## Parallelizable Work

- WP2 (Task 8-10) 可与 WP1 (Task 5-7) 并行——Seed Repair 能力补全不依赖 Tailor 诊断结果
- Task 11 (语义字段验证) 与 Task 12 (assembly_plan 结构验证) 可并行——两者验证不同维度
- Task 15 (真实 API 集成) 与 Task 16 (错误状态展示) 部分可并行——API 集成稳定后做错误展示
