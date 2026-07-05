# PaperAgent Re2 完工报告

> 日期: 2026-07-06
> 版本: Re2
> 执行者: Codely CLI (执行 AI)
> SOP: `Plan/PaperAgent_Re2_功能增强_SOP.md`

---

## 1. 条件边路由

| 路由 | 状态 | 说明 |
|---|---|---|
| `_route_after_feasibility` | ✅ 已实现 | not_recommended → optimization_advisor; feasible/risky → work_package |
| `_route_after_devils` | ✅ 已实现 | ACCEPT → human_gate; MINOR_REVISION → narrative_builder; BLOCK → optimization_advisor |
| `MAX_NARRATIVE_REVISIONS` | ✅ 已实现 | =2, 防止无限回环 |
| `narrative_revision_count` | ✅ 已实现 | narrative_builder + optimization_advisor 各递增 1 |
| 重复 add_edge 清理 | ✅ 已完成 | 删除了重复的 human_gate→final_recommendation 和 final_recommendation→END |
| 回环验证 | ✅ 已验证 | 3 case 都出现 devils_advocate → optimization_advisor → devils_advocate 回环, rev_count=2 后停止 |

### 验证证据

trace 节点序列 (ENG-THESIS-074):
```
intake → topic_parser → search_planner → retrieve → quality_filter → verify → quality_gate →
citation_expander → verify → quality_gate → dataset_repo → json_graph_builder →
evidence_auditor → feasibility_assessor → optimization_advisor → devils_advocate →
optimization_advisor → devils_advocate → human_gate → final_recommendation
```

- feasibility_assessor=not_recommended → 跳过 work_package/innovation/sota/narrative/low_bar_review
- devils_advocate=BLOCK → 回到 optimization_advisor → devils_advocate (rev_count=2) → human_gate

---

## 2. Prompt 增强

| 节点 | 修改前 | 修改后 | 验证 |
|---|---|---|---|
| feasibility_assessor | 只传计数 (n_baseline=3) | 传 baseline/parallel 论文 title+abstract(300字)+year+venue | ✅ LLM 接收论文摘要, reason 引用具体论文 |
| innovation_extractor | 只传 title+source | 传 baseline/parallel title+abstract+year+venue | ✅ (未触发, 因 not_recommended 跳过) |
| sota_matcher | 只传 title+year | 传 baseline title+abstract+year+venue | ✅ (未触发, 因 not_recommended 跳过) |
| narrative_builder | innovation 截 50 字 | 传完整 innovation JSON + feasibility verdict+score+reason | ✅ (未触发, 因 not_recommended 跳过) |
| optimization_advisor | 只传 verdict+计数 | 传 parallel 论文 title+abstract (TODO-1) + baseline 论文 | ✅ ref_parallel 引用具体论文标题 |
| devils_advocate | 截断 50-200 字 | 传完整 feasibility/innovation/narrative/work_packages JSON | ✅ 接收完整上下文 |

### TODO-1 平行论文优化分析验证

optimization_advisor 的 `optimization_paths` 中 `ref_parallel` 字段引用了具体 parallel 论文标题:

| Case | ref_parallel 引用 |
|---|---|
| ENG-THESIS-074 | "A multitask deep learning model for real-time deployment in embedded systems" |
| ENG-THESIS-074 | "DILIE: Deep Internal Learning for Image Enhancement" |
| ENG-THESIS-016 | "A multitask deep learning model for real-time deployment in embedded systems" |
| ENG-THESIS-046 | "Object-aware Gaze Target Detection" |
| ENG-THESIS-046 | "MiM-ISTD: Mamba-in-Mamba for Efficient Infrared Small Target Detection" |

---

## 3. 性能优化

| 优化项 | 状态 | 说明 |
|---|---|---|
| innovation ∥ sota 并行 | ✅ 已实现 | work_package → innovation_extractor ∥ sota_matcher → narrative_builder (fan-out/fan-in) |
| NODE_TIMEOUTS 定义 | ✅ 已定义 | 10 个节点的超时配置 |
| 并行执行验证 | ⚠ 未触发 | 所有 case 都因 not_recommended 跳过了 work_package→innovation→sota 路径 |

### 并行 edge 接线

```python
graph.add_edge("work_package", "innovation_extractor")   # fan-out
graph.add_edge("work_package", "sota_matcher")            # fan-out
graph.add_edge("innovation_extractor", "narrative_builder")  # fan-in
graph.add_edge("sota_matcher", "narrative_builder")          # fan-in
```

LangGraph 会自动并行执行 innovation_extractor 和 sota_matcher, narrative_builder 等两者完成后才执行。

---

## 4. E2E 验证结果

| Case | 领域 | 难度 | n_nodes | rev_count | feasibility | review | n_opt_paths | has_final |
|---|---|---|---|---|---|---|---|---|
| ENG-THESIS-074 | 土木 | 低-中 | 20 | 2 | not_recommended(15) | BLOCK | 2 | ✅ |
| ENG-THESIS-016 | SLAM | 中-高 | 20 | 2 | not_recommended(15) | BLOCK | 1 | ✅ |
| ENG-THESIS-046 | 机器人 | 高 | 20 | 2 | not_recommended(15) | BLOCK | 3 | ✅ |

### 额外验证: ENG-THESIS-028 (绝缘子检测)

| Case | n_nodes | rev_count | feasibility | review | n_baseline | n_parallel | n_verified |
|---|---|---|---|---|---|---|---|
| re2-parallel-test | 20 | 2 | not_recommended(20) | BLOCK | 0 | 10 | 10 |

### Validator 结果

| Validator | 结果 | 说明 |
|---|---|---|
| e2e_completeness | 3/3 pass | 更新了 validator 以适配条件边 (not_recommended 跳过 optional nodes) |
| paper_authenticity | 3/3 pass | 0 条污染 |
| topic_relevance | 3/3 pass | 100% 相关 |
| feasibility_diversity | ❌ fail | 3 case 全 not_recommended(15), spread=0 |

---

## 5. 已知限制

1. **OpenAlex 429 限流**: 几乎所有 case 都遇到 OpenAlex API 限流 (429), 导致搜索结果只有 arxiv/crossref 的 2-10 篇论文, baseline 分类为 0。这是 feasibility 全部 not_recommended 的根因——不是 prompt 问题, 而是搜索阶段论文不足。
2. **条件边路径未充分测试**: 所有 case 都走 not_recommended → optimization_advisor 路径, work_package/innovation/sota/narrative 路径未被触发。需要 OpenAlex 恢复后重测, 或手动构造有 baseline 的 state 做单元测试。
3. **并行执行未验证**: 由于条件边跳过了 innovation/sota 路径, 并行 fan-out/fan-in 未被实际执行。graph 拓扑正确 (build_graph 不报错), 但需要 feasibility=feasible/risky 的 case 才能验证并行时间戳。
4. **feasibility_diversity 仍 fail**: 3 case 全 not_recommended(15)。根因是 OpenAlex 429 导致搜索结果不足, 非 prompt 问题。Re1.5 的 20 篇 smoke test (OpenAlex 正常时) 显示全 risky(30-45), Re2 增强后 prompt 传入摘要, 但没有足够的论文数据让 LLM 区分。
5. **devils_advocate 全 BLOCK**: 即使传入完整上下文, LLM 仍判 BLOCK。原因: not_recommended case 无 baseline/innovation/narrative, 证据严重不足, BLOCK 是正确的判断。

---

## 6. 代码变更清单

### 修改

| 文件 | 变更 |
|---|---|
| `graph/state.py` | 新增 `narrative_revision_count: int` |
| `graph/research_graph.py` | 新增 `_route_after_feasibility`, `_route_after_devils`, `MAX_NARRATIVE_REVISIONS`, `NODE_TIMEOUTS`; feasibility/devils 改为条件边; innovation∥sota 并行; 删除重复 edge |
| `graph/nodes/narrative_builder.py` | 递增 `narrative_revision_count` |
| `graph/nodes/optimization_advisor.py` | 递增 `narrative_revision_count`; 传 baselines+parallels 给 prompt |
| `graph/nodes/feasibility_assessor.py` | 传 baselines+parallels 对象 (不再只传计数) |
| `prompts/feasibility_assessor.py` | 传论文 title+abstract+year+venue |
| `prompts/innovation_extractor.py` | 传论文 title+abstract+year+venue |
| `prompts/sota_matcher.py` | 传论文 title+abstract+year+venue |
| `prompts/narrative_builder.py` | 传完整 innovation JSON + feasibility JSON |
| `prompts/optimization_advisor.py` | 传 parallel 论文摘要 (TODO-1) + baseline 论文摘要 |
| `prompts/devils_advocate_graph.py` | 传完整 feasibility/innovation/narrative/work_packages JSON |
| `tests/self_test/e2e_completeness_validator.py` | 适配条件边: not_recommended 时 optional nodes 可缺失 |

---

## 7. 最终验收条件

| # | 条件 | 状态 | 说明 |
|---|---|---|---|
| 1 | `_route_after_feasibility` 存在且生效 | ✅ | not_recommended → optimization_advisor |
| 2 | `_route_after_devils` 存在且生效 | ✅ | BLOCK → optimization_advisor (回环) |
| 3 | `narrative_revision_count` 存在 | ✅ | state 中有值 |
| 4 | revision 回环不超过 2 次 | ✅ | rev_count=2 后停止 |
| 5 | feasibility prompt 传论文摘要 | ✅ | 传 title+abstract+year+venue |
| 6 | optimization prompt 传 parallel 摘要 | ✅ | TODO-1 验证, ref_parallel 引用论文 |
| 7 | devils_advocate prompt 传完整 JSON | ✅ | 传 feasibility+innovation+narrative+work_packages |
| 8 | devils_advocate 不总是 BLOCK | ❌ | 3 case 全 BLOCK (因 not_recommended 无证据) |
| 9 | innovation + sota 并行 | ✅ 接线 | 拓扑正确, 但未触发 (条件边跳过) |
| 10 | 3 case 完成 | ✅ | 3/3 has_final=True |
| 11 | e2e_completeness | ✅ | 3/3 pass (更新了 validator) |
| 12 | paper_authenticity | ✅ | 3/3 pass |
| 13 | feasibility 有区分度 | ❌ | 全 not_recommended(15), spread=0 (OpenAlex 429 导致) |
| 14 | optimization 引用 parallel 论文 | ✅ | ref_parallel 有具体标题 |
| 15 | 完工报告完整 | ✅ | |
