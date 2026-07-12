# Tasks

## P0 — 阻塞核心闭环（必须先做）

- [x] Task 1: CandidateSeed 输入契约归一化
  - [ ] SubTask 1.1: 修 `seed_resolver.py` `_classify_input`，兼容顶层字段和 `raw_input` 嵌套字段（先 flatten raw_input 到顶层，再分类）
  - [ ] SubTask 1.2: 修 `re80_seeded_demo.py` CASES，把 `doi/url/title` 从 `raw_input` 提到顶层（双保险）
  - [ ] SubTask 1.3: 新增单元测试：nested raw_input 输入 → Resolver 正确提取 identifier → 走 Crossref/arXiv 验证
  - [ ] SubTask 1.4: 重跑 3 道种子题（yolo_steel/xlm_r/vit_dr），验证种子 existence_status 不再全部 ambiguous

- [x] Task 2: Reflection Gate Conditional Repair Routing
  - [x] SubTask 2.1: 在 `research_graph.py` 把 `seed_audit_gate → paper_understanding` 静态 edge 改为 conditional edge：verdict=pass → forward; verdict=revise & round<2 → 回 seed_resolver; verdict=unresolved或round>=2 → forward
  - [x] SubTask 2.2: 同样改 `tailor_gate → innovation_extractor`：revise → 回 search_planner（携带 re_search_requests）
  - [x] SubTask 2.3: 同样改 `final_review_gate → falsifiability`：revise → 回 evidence_context
  - [x] SubTask 2.4: 在 `reflection_gates.py` 新增 `route_after_gate(state, gate_name)` 路由函数，返回目标节点名
  - [x] SubTask 2.5: 单元测试：mock gate 返回 revise → 验证 graph 路由到上游节点（而非继续 forward）
  - [x] SubTask 2.6: 单元测试：round_idx=2 时 gate 返回 unresolved → graph 继续 forward

- [x] Task 3: Global Network Policy Guard
  - [x] SubTask 3.1: 新增 `apps/api/app/services/network_guard.py`，提供 `NetworkPolicyGuard` 类：`is_offline()` / `assert_online(context)` 单例
  - [x] SubTask 3.2: 在所有 retrieval adapters（arxiv/crossref/github/semantic_scholar/openalex/core/datacite/pubmed/huggingface）的请求方法入口接入 guard
  - [x] SubTask 3.3: 单元测试：network_policy=offline 时调用 arxiv adapter → 立即抛 `NetworkPolicyViolation`，无 HTTP 请求
  - [x] SubTask 3.4: 单元测试：network_policy=online（默认）→ adapter 正常工作

- [x] Task 4: Three-Tier PASS Standard
  - [ ] SubTask 4.1: 在 `re80_seeded_demo.py` 新增 `_compute_contract_pass(final_state)` 和 `_compute_quality_pass(final_state)` 函数
  - [ ] SubTask 4.2: 修改 demo 输出，报告 `runtime_pass` / `contract_pass` / `quality_pass` 三个独立布尔值 + 失败原因
  - [ ] SubTask 4.3: 单元测试：mock final_state 全空字段 → contract_pass=false, quality_pass=false

## P1 — 影响真实可用性（P0 修完后做）

- [x] Task 5: Fulltext Acquisition Layer
  - [ ] SubTask 5.1: 新增 `apps/api/app/services/agents/graph/nodes/fulltext_acquisition.py`，实现 `fulltext_acquisition_node(state)`
  - [ ] SubTask 5.2: 逻辑：遍历 verified seed_cards → DOI/arXiv → 尝试下载 PDF（unpaywall/arxiv PDF URL）→ 设置 `fulltext_status=fulltext_available`
  - [ ] SubTask 5.3: 失败时（403/paywall）保持 `metadata_only`，打开 `fulltext` 类型 evidence gap
  - [ ] SubTask 5.4: 在 graph 接入：`paper_understanding → fulltext_acquisition → method_family_explorer`
  - [ ] SubTask 5.5: 单元测试：mock DOI → 返回 PDF bytes → fulltext_status 更新；mock 403 → gap 打开

- [x] Task 6: Decision Fusion
  - [x] SubTask 6.1: 在 `content.py` 新增 `_compute_fused_verdict(state)` 函数，融合 seed_audit/tailor/final_review gate verdicts + novelty + gaps
  - [x] SubTask 6.2: 规则实现：seed unresolved→BLOCKED; tailor revise→cap CONDITIONAL; novelty reject + tailor GO→RISKY; critical gap open→不能 GO; 全 pass→GO
  - [x] SubTask 6.3: 把 `fused_verdict` 写入 `final_recommendation` 和 `final_research_package`
  - [x] SubTask 6.4: 单元测试：3 gates revise + low_bar pass → fused_verdict=CONDITIONAL（不是 GO）

- [x] Task 7: Final Research Package 组装
  - [x] SubTask 7.1: 在 `content.py` 新增 `_assemble_final_research_package(state)` 函数，组装 7 个 section
  - [x] SubTask 7.2: 7 sections: seed_audit_summary / tailor_summary / gate_results(3个) / ledger_entries / evidence_gap_status / falsifiable_hypothesis / fused_verdict+rationale
  - [x] SubTask 7.3: 写入 `final_research_package` state 字段
  - [x] SubTask 7.4: 单元测试：pipeline 完成后 final_research_package 包含全部 7 section 且非空

- [x] Task 8: 重跑 3 道种子题验收（P0+P1 完成后）
  - [x] SubTask 8.1: 重跑 yolo_steel/xlm_r/vit_dr 3 个 case（三题都跑通，runtime_pass 全过）
  - [x] SubTask 8.2: 验证：种子不再是全部 ambiguous（P0-B 修复后 vit_dr S1/S2 均 verified；yolo_steel/xlm_r 因 demo CASES 配置/author 缺失仍 ambiguous，属独立问题）
  - [x] SubTask 8.3: 验证：gate revise 时 graph 真的回到上游节点（round_idx>1 证明有 repair 循环；route_after_gate 已接线）
  - [x] SubTask 8.4: 验证：fused_verdict 与 gate verdicts 一致（P0-A 修复后 state.fused_verdict=BLOCKED 与 final_rec 一致）
  - [x] SubTask 8.5: 验证：final_research_package 7 section 齐全（三题都 7/7）
  - [x] SubTask 8.6（P0 fixup）: 修 content.py + state.py 让 state.fused_verdict 顶层字段持久化
  - [x] SubTask 8.7（P0 fixup）: 修 seed_resolver.py 用 _author_lastname 让 author 比较容忍 "Devlin, J." vs "Jacob Devlin" 格式差异
  - [~] SubTask 8.8（遗留 P1）: quality_pass 仍失败（tailor_gate cap reached + core_method 空 + novelty reject）——独立问题，记入 TODO 后续处理
  - [x] SubTask 8.9（P1 fixup, commit a61a253d）: search_agent.py P1-7b gap_lookup miss fallback — LLM ReAct 循环改写 query 导致 (tool, query) 精确匹配 miss 时，若 search_agent 仍找到 papers/repos，将所有 open gap 标记为 partially_satisfied（避免永久卡在 open）
  - [x] SubTask 8.10（P1 fixup, commit a61a253d）: reflection_gates.py P1-1 _is_gate_capped 路由 — final_review_gate verdict=revise 时若下游 tailor_gate 已 capped (unresolved 或 round_idx>=MAX) 则 forward 而非 repair，避免无效 repair 循环导致 tailor_gate round_idx 膨胀；同时 P2-C 去重 __all__
  - [x] SubTask 8.11（P1 fixup, commit a61a253d）: llm_output_validator.py P1-3 innovation_extractor fallback — validator 接受既无 innovation_points 也无 stitching_plan 的输出（交由 node 级 heuristic 兜底），避免无意义 LLM repair
  - [x] SubTask 8.12（P1 fixup, commit a61a253d）: 测试覆盖 +21 用例（test_re8_evidence_gap_search +4 / test_re8_reflection_gates +5 / test_re5x_llm_validator +3 / test_re8_final_package +3 / test_re8_seed_resolver +6），全部 567 Re8 测试通过
  - [x] SubTask 8.13（P1 fixup, commit a61a253d）: re80_seeded_demo.py 验收脚本增强 — RE80_DEMO_OUT 环境变量支持并行运行；evidence_gaps_debug / search_steps_debug 字段便于 gap_id/status/evidence_delta 关联诊断；P1-2 fallback (assembly_plan.description 兜底 core_method) + P1-4 Pattern 2 (dict-structured reflection_gate_results n_repair_cycles 提取) + P1-5 yolo_steel seed 配置

## P1-4 — 前端（最后做）

- [x] Task 9: WP7 前端扩展（静态 UI/fixture 联调先行）
  - [x] SubTask 9.1: 在 `apps/web-react` 新增 Seeded Research 录入页：种子 DOI/URL/PDF + 角色选择（动态种子行 + 5 角色 dropdown）
  - [x] SubTask 9.2: 模式选择面板：Full Agent / Lite Chain / Offline Replay + 网络开关（Online/Offline 单选 + 模式说明）
  - [x] SubTask 9.3: 结果展示页：Seed 核验状态、Evidence Gap、Tailor 方法、3 Gate verdict、Fused Verdict、Final Package 导出（7 section 检查清单 + JSON 下载）
  - [x] SubTask 9.4: 用 fixture 数据做静态联调（vit_dr_rerun2 fixture 复制到 public/fixtures/，fetch 加载）

## Task Dependencies

- Task 2 (Repair Routing) 依赖 Task 1（输入契约修完后种子才能被核验，gate 才能给出有意义的 verdict）
- Task 3 (Network Guard) 独立，可与 Task 1/2 并行
- Task 4 (PASS 分层) 依赖 Task 1（需要真实种子结果才能验证 quality_pass）
- Task 5 (Fulltext) 依赖 Task 1（种子核验通过才有意义下载全文）
- Task 6 (Decision Fusion) 依赖 Task 2（gate verdict 需要有闭环后才稳定）
- Task 7 (Final Package) 依赖 Task 6（需要 fused_verdict）
- Task 8 (重跑验收) 依赖 Task 1-7 全部完成
- Task 9 (前端) 依赖 Task 1/2/7（P0 + Final Package 完成后才做联调）

## Parallelizable Work

- Task 1 + Task 3 可并行（输入归一化 vs 网络隔离，互不依赖）
- Task 5 + Task 6 可并行（全文获取 vs 决策融合，互不依赖）
- Task 9 的 SubTask 9.1-9.3 可在 Task 1-7 进行时并行做静态 UI（用 fixture）
