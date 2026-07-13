# Re8.0 Close-the-Loop Checklist

## P0 — 阻塞核心闭环

- [x] CandidateSeed 输入归一化：`_classify_input` 能正确从 `raw_input` 提取 doi/url/title
- [x] Demo CASES 顶层字段 + raw_input 双保险已加
- [x] 新增单元测试：nested raw_input → Resolver 正确识别 identifier
- [x] 3 道种子题重跑后至少 1 个种子 `existence_status=verified`（P0-B 修复后 vit_dr S1/S2 均 verified）
- [x] seed_audit_gate 返回 revise 时 graph 路由回 seed_resolver（route_after_gate 已接线 + 单测覆盖）
- [x] tailor_gate 返回 revise 时 graph 路由回 search_planner
- [x] final_review_gate 返回 revise 时 graph 路由回 evidence_context
- [x] gate round_idx=2 时返回 unresolved，graph 继续 forward
- [x] `route_after_gate(state, gate_name)` 路由函数实现且被 conditional edge 调用
- [x] 单元测试：mock gate revise → 验证路由目标节点
- [x] 单元测试：mock gate unresolved → 验证 graph 继续 forward
- [x] `NetworkPolicyGuard` 类实现，`is_offline()` / `assert_online(context)` 单例可用
- [x] 所有 retrieval adapters 接入 guard（arxiv/crossref/github/semantic_scholar/openalex/core/datacite/pubmed/huggingface 共 9 个）
- [x] 单元测试：offline 模式调 arxiv adapter → 抛 `NetworkPolicyViolation`，无 HTTP
- [x] 单元测试：online 模式 → adapter 正常工作
- [x] `_compute_contract_pass(final_state)` 函数实现
- [x] `_compute_quality_pass(final_state)` 函数实现
- [x] Demo 输出报告 runtime_pass / contract_pass / quality_pass 三个独立布尔
- [x] 单元测试：空字段 final_state → contract_pass=false, quality_pass=false
- [x] P0-A fixup: `state.fused_verdict` 顶层字段持久化（content.py return + state.py TypedDict 字段定义）
- [x] P0-B fixup: `_author_lastname` 函数让 author 比较容忍 "Devlin, J." vs "Jacob Devlin" 格式差异

## P1 fixup — commit a61a253d（Re8.0 SOP goal-mode iteration 3 收尾）

- [x] P1-7b: search_agent.py gap_lookup miss fallback — LLM ReAct 循环改写 query 导致 (tool, query) 精确匹配 miss 时，若 search_agent 找到 papers/repos，将所有 open gap 标记为 partially_satisfied；3 题重跑后 gap_statuses={partially_satisfied:2}
- [x] P1-1 fixup: reflection_gates.py _is_gate_capped 路由 — final_review_gate verdict=revise 时若下游 tailor_gate 已 capped 则 forward 而非 repair，避免无效 repair 循环；同时 P2-C 去重 __all__ 条目
- [x] P1-3 fixup: llm_output_validator.py innovation_extractor fallback — 既无 innovation_points 也无 stitching_plan 时 validator 放行（交由 node 级 heuristic 兜底）
- [x] P1-2 fixup: re80_seeded_demo.py core_method fallback — _normalize_tailor_output 不写顶层 core_method，改读 assembly_plan.description
- [x] P1-4 fixup: re80_seeded_demo.py n_repair_cycles Pattern 2 — 支持 dict-structured reflection_gate_results
- [x] P1-5 fixup: re80_seeded_demo.py yolo_steel seed 配置修正
- [x] P1-7: re80_seeded_demo.py 新增 RE80_DEMO_OUT 环境变量支持并行运行
- [x] 测试覆盖 +21 用例：test_re8_evidence_gap_search (+4) / test_re8_reflection_gates (+5) / test_re5x_llm_validator (+3) / test_re8_final_package (+3) / test_re8_seed_resolver (+6)；全部 567 Re8 测试通过
- [x] Code review (subagent) verdict=YES，无 P0/P1 阻塞；P2-1 文档同步已处理（本小节）

## P1 — 影响真实可用性

- [x] `fulltext_acquisition_node` 节点实现
- [x] graph 接入：`paper_understanding → fulltext_acquisition → method_family_explorer`
- [x] DOI seed verified 后能下载 PDF（或打开 fulltext gap）
- [x] 单元测试：mock PDF 下载成功 → fulltext_status=fulltext_available
- [x] 单元测试：mock 403 → fulltext_status 保持 metadata_only + gap 打开
- [x] `_compute_fused_verdict(state)` 函数实现
- [x] Decision Fusion 规则实现：seed unresolved→BLOCKED; tailor revise→CONDITIONAL; novelty reject+tailor GO→RISKY; gap open→不能 GO
- [x] `fused_verdict` 写入 final_recommendation（也写入 state 顶层，P0-A 修复后）
- [x] 单元测试：3 gates revise + low_bar pass → fused_verdict=CONDITIONAL
- [x] `_assemble_final_research_package(state)` 函数实现
- [x] 7 section 齐全：seed_audit_summary / tailor_summary / gate_results / ledger / gap_status / hypothesis / fused_verdict
- [x] `final_research_package` 写入 state
- [x] 单元测试：pipeline 完成后 package 7 section 非空

## P1-4 — 前端

- [x] Seeded Research 录入页：DOI/URL/PDF + 角色选择（动态种子行 + 5 角色 dropdown）
- [x] 模式选择面板：Full/Lite/Offline + 网络开关（Online/Offline 单选）
- [x] 结果展示页：Seed 状态 + Gap + Tailor + Gate + Package 导出（7 section 检查清单 + JSON 下载）
- [x] 静态 fixture 联调通过（vit_dr_rerun2 fixture + TypeScript 编译通过 + npm run build 通过）

## 最终验收（Task 8）

### 第一轮（commit 317c38d0 / a61a253d，P1 fixup 后）

- [x] yolo_steel 重跑：runtime_pass + contract_pass（quality_pass 旧定义为 true，**但与 fused_verdict=BLOCKED 自相矛盾，属假阳性**，post-audit 已修正）
- [x] xlm_r 重跑：runtime_pass + contract_pass（quality_pass 同上假阳性）
- [x] vit_dr 重跑：runtime_pass + contract_pass + 种子 verified + seed_audit_gate pass + fused_verdict=BLOCKED 一致
- [x] final_research_package 7 section 齐全（3 题都验证）
- [x] trace events 中能看到 gate revise → 回到上游节点 → 再次 gate 的循环痕迹（round_idx>1 证明 repair 循环生效）
- [x] P0-A 修复：state.fused_verdict 顶层字段非 null（vit_dr 重跑2 验证 = "BLOCKED"）
- [x] P0-B 修复：种子 existence_status 升级到 verified（vit_dr S1/S2 均 verified）

### 第二轮（post-audit，commit c9ee3c62 + 73d97fab + e0239419，假阳性修正后）

权威验收结果存放于 `artifacts/re8_0/final/`：

- [x] xlm_r 重跑（`re80_rerun_xlm_r.json`，908s）：runtime_pass=true / contract_pass=true / **quality_pass=false**（fused_verdict=BLOCKED + seed_audit_gate unresolved + tailor_gate unresolved + low_bar=blocked）；P1-7b fallback 已删除，gap status 反映真实证据归因
- [x] vit_dr 重跑（`re80_rerun_vit_dr.json`，849s）：runtime_pass=true / contract_pass=true / **quality_pass=false**（fused_verdict=BLOCKED + tailor_gate unresolved）；gap-S1-competing_baseline=satisfied（有真实可追溯证据）
- [~] yolo_steel 重跑：第一轮因 `content.py:269` `data_source` list 崩溃（已由 commit e0239419 修复）；第二轮重跑进行中，结果待写入 `tmp_re13_eval/re80_rerun_yolo_steel_v2.json` 后同步到 `final/`
- [x] quality_pass 假阳性已消除：xlm_r 和 vit_dr 不再报告 `quality_pass=true` + `fused_verdict=BLOCKED` 的自相矛盾状态
- [x] P1-7b fallback 删除生效：evidence_gaps 中大部分 gap 保持 `open`（不再被无归因地批量标为 `partially_satisfied`），至少 1 个 gap (`gap-S1-competing_baseline`) 有真实可追溯证据 → `satisfied`

## 遗留问题（P1，不阻塞 Task 8 核心验收）

- [~] tailor_gate round_idx 超 cap（final_review_gate repair 循环重新触发 tailor_gate 导致计数累加；功能不受影响，cap 仍生效）——**已由 P1-1 fixup 缓解 final_review→tailor 路径**；tailor 自身 repair 循环的 round_idx 膨胀仍可能存在
- [ ] tailored_method.core_method 为空（tailor 节点输出质量问题，需独立排查 prompt/schema）——re80_seeded_demo.py 已通过 P1-2 fixup (assembly_plan.description) 兜底读取；post-audit 第二轮重跑确认 xlm_r/vit_dr 的 `core_method` 仍为空，根因是 `tailor_skill_adapter` LLM 输出质量问题，非假阳性。下一阶段重点：先验证 paper_understanding 是否消费 fulltext_acquisition 下载的 PDF，再调 Tailor Prompt/Schema（参见 spec.md "Recommendation: Tailor 上游输入完整性先于 Prompt 调优"）
- [~] innovation_extractor schema 反复失败 → novelty_review_verdict=reject（prompt/schema 问题，下游放大器）——**已由 P1-3 fixup 在 validator 层部分缓解**；node 级 heuristic 输出质量仍需独立排查
- [ ] repair_cycles_detected 检测盲区（unresolved 非 revise 不计数；metric 准确性问题）
- [x] yolo_steel S1 demo CASES 配置错误（arxiv 2305.11527 实际是 InstructIE 论文，不是 YOLOv8）——**已由 P1-5 fixup 修正 seed 配置**（commit a61a253d）
- [~] xlm_r 种子 author 字段缺失导致仍 ambiguous（demo CASES 应补 author 或改用 _author_lastname fallback）——**已由 P0-B fixup (_author_lastname) 部分缓解**；author 比较容忍格式差异，但 demo CASES 仍建议补全 author 字段
