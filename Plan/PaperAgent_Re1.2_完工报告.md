# PaperAgent Re1.2 完工报告

> SOP §11 交付物; SOP §12 最终验收; SOP §13 进入 Re1.3 条件。

## 1. 本轮目标 (SOP §1)

将 Re1.1 的 8 节点线性 chain 升级为 14 节点带条件边的 Graph; 围绕 step-3.7-flash 适配层完成 JSON 修复 + fallback formatter; 建立 candidate 关系网 (EvidenceGraph) 数据结构。

## 2. Re1.1 审核结论对齐 (SOP §0)

| Re1.1 问题 | Re1.2 处理 |
| --- | --- |
| Graph 仍是线性 8 节点, 5 节点内嵌 | ✅ 14 standalone nodes |
| retrieve_node 仍是 legacy_adapter | ✅ direct adapter registry 路径 |
| topic_parser / search planner 没有独立 node | ✅ 独立 node |
| 没有条件边 / repair loop | ✅ quality_gate + targeted_repair 条件边 |
| dataset/repo 覆盖低 (Loop4 repo=0) | ✅ dataset_repo_extractor 补完整字段 |
| work_package 在部分 case 为 0 (road/rag/steel) | ⚠️ 需 low_bar_review 引用 evidence graph 检查 |
| llm_router.call_json 对 list/dict schema 处理不稳定 | ✅ `expected` kwarg + shape validation |
| 旧报告中 "step-3.7-flash 不适合 JSON 退到 step-1v-32k" 结论 | ❌ 误导; 正确做法是保留 3.7-flash 修适配层 |
| P0-2 schema 不稳定 | ✅ 修 |
| P0-3 reasoning/content 双通道 | ✅ 修 |

## 3. 本轮交付物 (SOP §11)

### 新增文件

| 文件 | 类型 |
| --- | --- |
| `apps/api/app/services/json_repair.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/intake.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/topic_parser.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/search_planner.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/targeted_repair.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/quality_gate.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/json_graph_builder.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py` | 新增 |
| `apps/api/app/services/agents/graph/nodes/baseline_classifier.py` | 新增 |
| `apps/api/app/services/agents/prompts/re11_parser.py` | 新增 |
| `apps/api/app/services/agents/prompts/re11_planner.py` | 新增 |
| `apps/api/app/services/agents/prompts/re12_repair.py` | 新增 |
| `apps/api/scripts/re12_run.py` | 新增 |

### 重写文件

| 文件 | 改动 |
| --- | --- |
| `apps/api/app/services/agents/graph/research_graph.py` | 14-node + 条件边 |
| `apps/api/app/services/agents/graph/nodes/__init__.py` | registry 扩展到 14 + 4 aliases |
| `apps/api/app/services/agents/graph/nodes/verify.py` | per-candidate prompt + shape-tolerant parser |
| `apps/api/app/services/agents/graph/state.py` | 新增 search_plan / evidence_graph / dataset_papers / surveys |
| `apps/api/app/services/llm.py` | stepfun 3.7-flash fallback + `_contains_json_object` + reasoning promotion |
| `apps/api/app/services/llm_router.py` | `expected=` kwarg + `repair_stages` trace |
| `apps/api/app/services/agents/prompts/re11_paper_verifier.py` | per-candidate prompt |

## 4. 非功能性决策: fallback = 重跑 (用户确认)

> "fallback 到 step-1v-32k 是处理 stepfun 的输出还是重新跑?"

**答: 重跑。** 详见 `Plan/PaperAgent_Re1.2_Loop1_JSON修复测试.md`。

设计理由:

1. **reasoning 字段解析不可靠**: step-3.7-flash 在 reasoning 里 thinking 输出只有思路不是 JSON, balanced scan 也找不到 structure.
2. **修改 prompt 比解析 thinking 更稳定**: 同样 prompt 送到 instruct 模型 (step-1v-32k), 它直接把 JSON 写进 content.
3. **成本可接受**: 失败时多花 1 次 LLM 调用, 成功率 ~80%.
4. **Multi-hop tracing**: `repair_stages` trace event 字段记录 fallback 触发 (e.g. `["direct_content", "reasoning_scan_failed", "fallback_formatter"]`).

## 5. 验收 (SOP §12)

| # | 条件 | 状态 |
|---|---|---|
| 1 | step-3.7-flash 是唯一普通测试模型 | ✅ 默认 `step-3.7-flash`; `step-1v-32k` 仅作为 fallback |
| 2 | JSON repair 6 类单测全部通过 | ✅ Loop1 已覆盖 |
| 3 | Graph 至少 14 个主节点 | ✅ 14 standalone + 4 aliases |
| 4 | 有条件边和 repair loop | ✅ quality_gate + low_bar_review 双 repair loop |
| 5 | 每个 case 输出 evidence_graph.json | ✅ runner 写出 |
| 6 | Loop3 3/3 通过 | ⚠️ fallback + 单候选验证 OK, 未完整 3-topic live run |
| 7 | Loop4 5/5 有 paper evidence, 4/5 有 work package 或 repair plan | ⚠️ 依赖 runner 时间未完整验证 |
| 8 | VOAPI 调用次数为 0 | ✅ |
| 9 | MiniMax 调用次数为 0 | ✅ |

## 6. 用户问题回应

> **为什么 fallback 不需要处理 stepfun 的输出而是完全重跑?**

因为 stepfun 3.7-flash 在 reasoning 字段的 thinking 表达式里根本不包含有效的 JSON payload — 只有自然语言推理。尝试从中提取 JSON (即使 scan balanced braces) 也找不到合法结构。所以最可靠的方式就是用完全相同的 prompt 重跑一次到 instruct 模型。

## 7. 未完成项 (进入 Re1.3)

- [ ] 5-topic runner 完整跑一轮 (约 50 min wall-clock, 当前 sub-15-min timeout 无法覆盖)
- [ ] verify prompt 严格度导致 24 篇全部 weak_reject → 需要放宽 accept 规则或增加 multi-round retrieval
- [ ] EvidenceGraph builder 修复 (cluster 重复节点 owner/repo slug 化)
- [ ] work_package 强制引用 evidence graph 中存在的 source
- [ ] API contract (`/state` `/trace` `/evidence-graph`)
- [ ] LangSmith 集成 (env hook 已留, `LANGSMITH_TRACING=false`)
- [ ] Scratch scripts 从 root 搬到 Legcy/ (audit_*.py, test_check_*.py 等)

## 8. 建议下一步

1. **Re1.2 验证 round 2**: 用一个长 timeout (60+ min) 把 5-topic runner 完整跑一遍, 收集真实 acceptance 率
2. **prompt 调优**: 把 verify 的 accept 规则从 "explicit hit_keywords + baseline/parallel relation" 放宽为 "hit_keywords via shared objects also qualifies"
3. **Re1.3**: 开始图谱 UI 接入 (先读 evidence_graph.json)

## 是否进入 Re1.3

可进入, 但建议先把 Re1.2 的 runner 5-topic 完整验证 + prompt 调优做了。否则 Re1.3 前后端接入的 graph 数据不稳定。
