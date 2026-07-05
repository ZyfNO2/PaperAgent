# PaperAgent Re1.3 Loop 5 — 真实 3 样例测试报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 测试内容

复用 Re1.2 Loop3 的 3 个题目进行端到端测试:

1. `基于YOLOv5的钢材表面缺陷检测研究`
2. `基于深度学习的视觉SLAM语义地图的研究`
3. `基于大语言模型的医学问答可信度评估方法研究`

## 执行状态

> **注意**: 真实样例端到端测试需要 LLM API 密钥 (StepFun/DeepSeek) 和网络访问 (Semantic Scholar API)。以下为代码路径验证和静态分析结果。

## 代码路径验证

### Graph 流程验证

Re1.3 的 graph 流程 (通过代码审查确认):

```
START → intake → topic_parser → search_planner → paper_retriever
  → quality_filter (🆕) → verify (第一轮) → quality_gate
  → citation_expander (🆕) → verify (第二轮) → quality_gate (第二轮)
  → dataset_repo_extractor → evidence_graph_builder → baseline_classifier
  → work_package → low_bar_review → human_gate → final_recommendation → END
```

### 条件路由验证

- `_route_after_quality_gate`:
  - 第一轮 (citation_expansion_done=False): n_papers<1 → repair; n_papers>=1 → citation_expander
  - 第二轮 (citation_expansion_done=True): n_papers<1 → blocked; n_papers>=1 → continue

### 预期行为

| # | 检查项 | 预期 | 验证方式 |
|---|---|---|---|
| 1 | 每个 case paper >= 3 | 引文扩展后应增加论文数 | state.json verified_papers |
| 2 | 词条/概念页被过滤 | quality_filter 过滤非论文 | filter_results.dropped_items |
| 3 | 引文扩展产出 >= 5 篇 | 至少 1 case | expanded_papers |
| 4 | 至少 1 case 发现综述 | survey 识别 | surveys_found |
| 5 | work_package 不为空 | 后续节点正常 | work_packages |

## 单元测试覆盖

以下单元测试 (mock 环境) 全部通过, 覆盖了核心路径:

- Loop 1: quality_filter 6 类候选 (7 tests passed)
- Loop 2: citation_expander 种子选取+扩展 (13 tests passed)
- Loop 6: 自动种子选取 (7 tests passed)

## 结论

Loop 5 的代码路径和逻辑已通过单元测试验证。真实 LLM 端到端测试需要 API 密钥和网络环境, 在当前环境下无法执行完整的 3 样例 E2E 测试。

代码审查确认:
- ✅ quality_filter 在 retrieve 之后、verify 之前执行
- ✅ citation_expander 在 quality_gate 通过后执行
- ✅ 第二轮 verify 验证扩展论文
- ✅ 扩展论文经过 verify 后并入 verified_papers
- ✅ citation_expansion_done flag 防止无限循环
