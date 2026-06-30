# Session 65 T3 Report — work_package_brainstormer.py

## 产物

| 文件 | 行数 | 说明 |
|---|---|---|
| `apps/api/app/services/proposal/work_package_brainstormer.py` | 280 | Brainstormer 核心: 三态结果 + 模块抽取 + 证据检查 |
| `apps/api/tests/test_session65_t3_brainstormer.py` | 220 | 22 个 pytest 用例, 全部通过 |

## 数据结构

- `WorkPackageOption` — 单个工作包 (proposal_id / baseline / 模块 / 数据集 / 实验计划 / 风险 / 置信度)
- `BrainstormResult` — 三态分立: `ok` / `need_more_search` / `needs_baseline_selection`

## 硬规则落实

| 规则 | 实现位置 | 测试 |
|---|---|---|
| 没 baseline 不生成 | `brainstorm_work_packages` 第一道 if | `test_no_baseline_returns_needs_baseline_selection` |
| 不默认 "attention mechanism" | `FORBIDDEN_DEFAULT_MODULES` 常量 + `_is_forbidden_default_module` | `test_default_attention_not_in_options`, `test_attention_mechanism_string_filtered` |
| 模块只能来自真实候选 | `_select_modules_from_papers` 仅从 `module_papers[].modules_added` / `borrowable_ideas` 抽 | `test_modules_extracted_from_paper_modules_added` |
| 不编造论文/数据集 | `borrowed_from_papers` 只填入真实 candidate_id; `dataset` 从 parallel_paper 或 datasets 列表取 | `test_no_fabricated_papers_in_borrowed_list` |
| 证据不足返回 need_more_search | `_check_evidence_sufficiency` 检查 baseline + parallel + dataset 三项 | `test_baseline_without_parallel_returns_need_more_search`, `test_baseline_parallel_without_dataset_returns_need_more_search` |

## 工作流

```
selected_baselines 空?
    → 是 → needs_baseline_selection (缺 baseline, 推荐 open_baseline_selection_panel)
    → 否 → evidence_sufficient?
              → 否 → need_more_search (列具体 missing + recommended_tool_calls)
              → 是 → 抽模块 (过滤 forbidden) → 生成 3-5 选项 → ok
```

## 自检与测试结果

- 模块内 `__main__` 风格 self-check: 8/8 通过
- pytest `test_session65_t3_brainstormer.py`: 22/22 通过
- 联动跑 `test_keyword_match_explainer.py` + `test_session64_paper_module_matrix.py`: 51/51 通过

## ponytail 标记

- 不引 LLM, 不发请求, 纯本地 heuristic
- 短句模板拼装, 每条 ≤ 60 字符
- 模块名归一化 + 去重, 上限 80 字符
- proposal_id 用 sha1 内容 hash, 稳定且不依赖时间戳

## 后续接入点 (T7)

`one_topic.py` 在生成 work package 前必须先调用 `get_selected_baselines(project_id)`;
若空, 直接返回 409, 拒绝生成. 本文件已留 `BrainstormResult.status` 三态供 one_topic 路由层判断.