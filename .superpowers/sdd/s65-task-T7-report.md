# Task T7 Report: one_topic.py — no work package before baseline selected

## Status: DONE

## What was implemented

Modified `apps/api/app/services/one_topic.py::recommend_proposal()`:

**硬规则落地:**

1. **没 baseline → 不生成 work_packages** (硬规则 1)
   - 函数开头先调 `get_selected_baselines(project_id)` 查 `baseline_selection` 状态
   - 若 `selected == []` → 直接返回 `ProposalRecommendation(work_packages=[], pivot_routes=[])`
   - 推荐理由里追加 `"暂不生成工作包：请先从候选论文 / 仓库中选择主 Baseline"` (与 task spec 文案一致)

2. **不再硬编码 "注意力机制 / 轻量化模块"** (硬规则 2)
   - 删掉了原 `wp2_method = "轻量化模块" if "yolo" in method.lower() else "注意力机制"` 这种硬编码分支
   - 选了 baseline 之后, 调 `brainstorm_work_packages(...)` 生成选项, 模块只来自 `module_papers` / `parallel_papers` 的真实 `modules_added` / `borrowable_ideas`
   - 极端兜底: 即使 brainstorm 没产出 options, 也不补 "attention" 这种通用词, 只用 `baseline_name + dataset` 拼最简 WP

3. **模块从真实证据来** (硬规则 3)
   - 在调用 brainstormer 前, 按 `literature_role` 过滤 `ev.papers`:
     - `parallel_application_paper` → 喂给 `parallel_papers`
     - `module_improvement_paper` → 喂给 `module_papers`
   - datasets / baselines 透传 `ev.datasets` / 选定的 `selected`
   - `user_constraints={}` (T7 不收集用户约束, 用空 dict)

## Flow

```
recommend_proposal(req, keywords, ev, feas)
├─ build reasons (heuristic 模板)
├─ get_selected_baselines(project_id)   ← baseline_selection 查
│
├─ selected == []  → 返回 empty ProposalRecommendation
│                    reasons 追加 "请先选 baseline"
│                    pivot_routes=[], work_packages=[]
│
└─ selected != []  → brainstorm_work_packages(
                        selected_baselines=[s.model_dump() for s in selected],
                        parallel_papers=[parallel_application_paper papers],
                        module_papers=[module_improvement_paper papers],
                        datasets=[ev.datasets],
                        user_constraints={},
                     )
                     ├─ status="ok"  → 映射 options → WorkPackageSuggestion
                     │                  (title 来自 opt.title, 不补 attention)
                     ├─ status="need_more_search" → reasons 加 evidence gap
                     └─ status="needs_baseline_selection" → 不应出现 (兜底)
```

## 启发式兜底 (无 module_paper 时)

若 brainstorm 因证据不足返回 `need_more_search` 或没 options, 走最简兜底:

```python
wp = WorkPackageSuggestion(
    wp_id="WP1",
    title=f"复现 {bl_name} baseline 并建立基线指标",   # ← baseline 名
    research_question=f"{bl_name} 在 {primary_dataset} 上的标准基线表现?",
    method_approach=f"采用 {bl_name} 标准实现, 在 {primary_dataset} 上训练/验证.",
    data_source=primary_dataset,
    experiment_plan=f"按标准 split 训练, 报告 {metric} 等指标.",
    chapter="第三章",
)
```

注意: 兜底里**绝不**出现 "attention / 注意力机制 / 轻量化" 这种通用词, 只用真实 `baseline_name`。

## LLM 路径

原 `req.prefer != "heuristic"` 走 LLM 的分支保留, 但**只在有 baseline 时**才调:
- `baseline_names` 改用 `[s.candidate_id for s in selected]`
- `has_baseline=True`
- LLM 失败 → 落到上面 brainstorm + 兜底 路径

## Pivot routes

未选 baseline 时 `pivot_routes=[]` (pivot 依赖 baseline 决策, 早期没意义)。

## Tests added

新建 `apps/api/tests/test_session65_t7_work_package_baseline.py` (5 个 case, 全过):

| Test | 验证 |
|---|---|
| `test_no_baseline_no_work_packages` | 没 baseline → work_packages==[], 推荐理由含 "请先从候选论文", 不出现 attention/轻量化 |
| `test_with_baseline_uses_brainstormer` | 选 baseline → 用 brainstormer 生成 WP, 模块从 module_papers 来, 不硬编码 |
| `test_baseline_but_no_module_paper_no_hardcoded_attention` | 有 baseline 但无 module_paper → 兜底 WP 不出现 attention 兜底词 |
| `test_no_project_id_override_does_not_error` | 没传 project_id_override → 用 "ot_pending" 兜底, 不报错, 不误判已选 |
| `test_recommended_topic_always_present` | 无 baseline 时 recommended_topic 仍应有内容 (只是不挂 WP) |

## Tests updated

`apps/api/tests/test_one_topic_api.py::test_analyze_yolo_steel_happy_path`:
- 改前: `assert len(rec["work_packages"]) >= 1`
- 改后: `assert rec["work_packages"] == []` + 断言推荐理由含 "请先从候选论文"
- 原因: 新契约明确 "未选 baseline 不生成 WP", 老断言是旧契约的遗物

## Test run

```
$ python -m pytest apps/api/tests/test_session65_t7_work_package_baseline.py -v
============================= 5 passed in 0.44s ==============================
```

`test_analyze_pcb_bridge_skin_match_known_datasets` 失败是**预存在**的 Windows console GBK 编码问题 (与 T7 无关, master 分支也一样失败), 已确认是 pre-existing 故障。

## Files changed

- `apps/api/app/services/one_topic.py` — `recommend_proposal()` 全文重写 (128 → 199 行)
- `apps/api/tests/test_one_topic_api.py` — `test_analyze_yolo_steel_happy_path` 适配新契约
- `apps/api/tests/test_session65_t7_work_package_baseline.py` — 新建 (5 tests)

## Hard rules check

| Rule | Status |
|---|---|
| 1. If no baseline selected, MUST NOT generate work packages | DONE — `if not selected: return ProposalRecommendation(work_packages=[])` |
| 2. Default "attention mechanism" MUST NOT be in module candidates | DONE — `wp2_method = "轻量化模块" if "yolo" ... else "注意力机制"` 整段删除, 改用 brainstormer + baseline_name 兜底 |
| 3. Modules must come from parallel papers or user selection | DONE — brainstormer 内部 `_select_modules_from_papers` 只从 `module_papers` 抽 `modules_added` / `borrowable_ideas`, 有 `FORBIDDEN_DEFAULT_MODULES` 白名单禁掉 attention |
