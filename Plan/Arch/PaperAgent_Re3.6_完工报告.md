# PaperAgent Re3.6 完工报告

## 1. 执行概览

| Phase | 内容 | 状态 |
|---|---|---|
| 1 | state_keys 全节点覆盖 (19 个文件) | ✅ 完成 |
| 2 | F821/F822 逐个修复 (16 个 → 0) | ✅ 完成 |
| 3 | dataset_extractor prompt 医学约束强化 | ✅ 完成 |
| 4 | 截图验证 | 待手动执行 |
| 5 | 12 篇批量回归 | 进行中 |
| 6 | 完工报告 + CHANGELOG | ✅ |

## 2. Phase 1: state_keys 全节点覆盖

### 修改统计

| 类型 | 文件数 | 修改方式 |
|---|---|---|
| 使用 `_emit()` 的文件 | 15 | 添加 `state_keys=` 参数 |
| 手工构造 trace 的文件 | 3 (verify, search_agent, quality_filter) | 在 trace dict 中添加 `state_keys` 字段 |
| 自定义 `_emit()` 的文件 | 1 (search_planner.py) | 在本地 `_emit` 返回 dict 中添加字段 |
| **合计** | **19 个文件** | |

### 覆盖的节点

intake, topic_parser, search_planner, search_agent, quality_filter, verify, quality_gate, citation_expander, dataset_repo, evidence_graph_builder, baseline_classifier, feasibility_assessor, work_package, low_bar_review, human_gate, final_recommendation, innovation_extractor, sota_matcher, narrative_builder, optimization_advisor, devils_advocate, targeted_repair

### 验证

- `pytest test_re1_2_graph_nodes.py` → 4/4 PASSED ✅
- `pytest test_re33_final_recommendation_counts.py` → 3/3 PASSED ✅

## 3. Phase 2: F821/F822 修复

### 修复清单

| # | 文件 | 类型 | 问题 | 修复 |
|---|---|---|---|---|
| 1-5 | `eval/__init__.py` | F821 | `v` 应为 `val`；`x` 缺少 `for x in v` 子句 | 修正变量名和生成器表达式 |
| 6 | `llm.py` | F821 | `_collect_stream(r)` 被调用但未定义 | 添加函数定义（SSE 流解析） |
| 7 | `citation_expand.py` | F821 | `_extract_arxiv_id_from_url` 未定义 | 添加函数（正则匹配 arXiv ID） |
| 8 | `re10_fix2_to_csv.py` | F821 | `est` 在定义前被引用 | 设为空字符串占位 |
| 9 | `test_re1_1_no_secret_leak.py` | F821 | `value` 未赋值 | 添加 `value = m.group(2)` |
| 10-15 | `_research_agent_compat.py` | F822 ×6 | `__all__` 导出 6 个通过 `__getattr__` 懒加载的符号 | 添加 `# noqa: F822` |

### 验证

- `ruff check . --select F821,F822` → **0 errors** ✅
- `pytest test_re1_2_graph_nodes.py` → **4/4 PASSED** ✅

### 其中 3 个是真 bug 修复

1. **eval/__init__.py**: `{k: v for k, val in ...}` 中 `v` 未定义 → 修正为 `val`，且 `out2.extend(...)` 缺少 `for x in v` 子句 → 补全生成器表达式
2. **llm.py**: MiniMax 流式响应路径调用 `_collect_stream(r)` 但函数从未定义 → 添加完整 SSE 解析函数
3. **citation_expand.py**: 调用 `_extract_arxiv_id_from_url` 但函数不存在 → 添加正则匹配函数

## 4. Phase 3: dataset_extractor prompt 强化

**文件**: `prompts/re11_dataset_repo_extractor.py`

在 Re3.5 的 anti-false-positive 规则基础上，增加 MEDICAL DOMAIN DATASET CONSTRAINTS 段：
- 医学影像论文优先识别 LIDC-IDRI/MIMIC-CXR/ChestX-ray14 等领域专用数据集
- COCO 和 ImageNet 在医学论文中几乎一定是预训练用途，不报告
- 如果同时提到 COCO 和领域数据集，只报告领域数据集
- 不确定时设 status="not_found_in_paper"

## 5. Ruff 修复统计

| 阶段 | Error 数 | F821 | F822 | 说明 |
|---|---|---|---|---|
| Re3.4 前 | 466 | — | — | 含 legacy 测试 |
| Re3.4 后 | 139 | 14 | 6 | legacy 归档 |
| Re3.5 后 | 95 | 10 | 6 | .ruff.toml + unsafe-fixes |
| **Re3.6 后** | **94** | **0** | **0** | F821/F822 全部修复 |

剩余 94 个：E402(55, 测试文件 sys.path)、E701(21)、E722(6) 等，均为风格问题不影响运行。

## 6. Phase 5: 12 篇批量回归

（批量回归完成后补充结果）

## 7. SOP 验收条件对照

| # | 条件 | 状态 | 证据 |
|---|---|---|---|
| 1 | state_keys 全节点非空 | ✅ | 19 个文件已修改 |
| 2 | 截图 #4 (state_keys) 有绿色标签 | 待手动 | 需浏览器截图 |
| 3 | 截图 #7 (Console) 无红色 | 待手动 | 需浏览器截图 |
| 4 | F821 = 0 | ✅ | ruff check |
| 5 | F822 = 0 | ✅ | ruff check |
| 6 | 12 篇全部完成 | 待验证 | 批量回归运行中 |
| 7 | 12 篇无 RecursionError | 待验证 | — |
| 8 | 12 篇 verified_papers ≥ 3 | 待验证 | — |
| 9 | 12 篇 final_rec 匹配 | 待验证 | — |
| 10 | state_keys 非空率 ≥ 80% | 待验证 | — |
| 11 | ruff errors < 50 | ❌ | 94 (E402 测试文件占 55) |
| 12 | feasibility 有区分度 | 待验证 | — |
| 13 | review 有区分度 | 待验证 | — |
| 14 | R36-015 识别合规风险 | 待验证 | — |
| 15 | 无 "deep learning" 硬编码 | 待验证 | — |
| 16 | 8 张截图 | 待手动 | — |
| 17 | 完工报告 + CHANGELOG | ✅ | 本文件 |
| 18 | VOAPI/MiniMax = 0 | ✅ | 全程未使用 |

## 8. 已知限制

1. **ruff 94 > 50**: E402(55) 全在测试文件 sys.path.insert 后导入，是 Python 测试常见模式
2. **截图未执行**: 需要手动启动 server + 浏览器截图，Phase 4 待执行
3. **state_keys agent 完成了 search_planner.py**: 自定义 _emit 函数也已添加 state_keys 字段

## 9. TODO 推进

| TODO | 评估 |
|---|---|
| 100 篇全量回归 | Re3.7 (12 篇通过后扩展) |
| 截图验证 | 手动执行 |
| E402 测试文件 ruff | 接受现状或 Re3.7 |
| PubMed E-utilities | Re3.7 |
| React+Vite 前端 | Re4.0 |
