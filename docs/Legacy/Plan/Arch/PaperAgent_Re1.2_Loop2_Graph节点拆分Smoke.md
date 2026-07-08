# PaperAgent Re1.2 Loop 2 Graph 节点拆分 Smoke

> SOP §14 Loop 2: 验证 14 个节点注册并 fire。

## 实际 graph 拓扑 (research_graph.py)

graph 类型: 14 节点 (Re1.1 仅 8 节点) + START + END。

```
START → intake → topic_parser → search_planner → paper_retriever → paper_verifier
      → quality_gate
          ├─ repair ─→ targeted_repair → paper_retriever (loop)
          ├─ continue ─→ dataset_repo ─→ evidence_graph_builder ─→ evidence_auditor
                         → work_package → low_bar_review
                            ├─ repair ─→ targeted_repair (loop)
                            ├─ ready ─→ human_gate ─→ final_recommendation ─→ END
                            └─ blocked ─→ final_recommendation ─→ END
          ├─ blocked ─→ final_recommendation ─→ END
          └─ END
```

## 验证结果

### 14 节点 registry test (test_re1_1_research_graph_smoke.py 适配版)

```python
expected = {
    "intake", "topic_parser", "search_planner", "paper_retriever",
    "paper_verifier", "quality_gate", "targeted_repair", "dataset_repo",
    "evidence_graph_builder", "evidence_auditor", "work_package",
    "low_bar_review", "human_gate", "final_recommendation",
}
assert expected.issubset(graph_nodes.REGISTRY)
```

**实际**: ✅ 所有 14 节点注册成功 + 4 个 Re1.1 compat aliases (retrieve/verify/dataset_repo/work_package/evidence_auditor) 也保留。

### 编译 + Mock 执行 Re1.1 测试 (全覆盖)

`apps/api/tests/test_re1_1_research_graph_smoke.py::test_graph_compiles_and_runs_offline`

注入:

- 3 baseline_paper candidates (mock `_run_legacy_retrieval`)
- `call_json` 返回 shape-aware mock (根据 prompt 关键词)
- `_call_verifier` mock 返回 3 verdicts

通过条件: 14 节点 all fire + final_recommendation 存在。

**结果**: ✅ 5/5 tests pass (timing ~25s)

### Report (质量门) 关键路径

| path | quality_gate_route | 触发条件 |
| --- | --- | --- |
| 正常 | continue | verified_papers >= 1 AND quarantine ratio < 0.4 |
| 证据不足 | repair | verified_papers < 1 OR quarantine ratio > 0.4 |
| 建议被 block 且 cap exhausted | blocked + repair_plan | low_bar_review.status=blocked AND repair_rounds>=MAX |

### Trace 样例 (Re1.1 后向兼容)

```text
[intake] 0ms → [topic_parser] 30s → [search_planner] 22s → [paper_retriever] 47s
→ [paper_verifier] 150s (fallback 时间) → [quality_gate] 0ms → [targeted_repair] 33s
→ [paper_retriever] 50s → ...
```

## 文件清单 (apps/api/services/agents/graph/nodes/)

| 文件 | 节点 | 类型 |
| --- | --- | --- |
| intake.py | intake_node | Re1.2 新增 standalone |
| topic_parser.py | topic_parser_node | Re1.2 新增 standalone |
| search_planner.py | search_planner_node | Re1.2 新增 standalone |
| targeted_repair.py | targeted_repair_node | Re1.2 新增 standalone |
| quality_gate.py | quality_gate_node | Re1.2 新增 standalone |
| json_graph_builder.py | json_graph_builder_node | Re1.2 新增 standalone |
| dataset_repo_extractor.py | dataset_repo_extractor_node | Re1.2 替代 content.dataset_repo_node |
| baseline_classifier.py | baseline_classifier_node | Re1.2 替代 content.evidence_auditor_node |
| retrieve.py | retrieve_node (alias paper_retriever) | 保留 |
| verify.py | verify_node (alias paper_verifier) | 重写 per-candidate |
| content.py | work_package_node / low_bar_review_node / human_gate_node / final_recommendation_node | 保留 |
