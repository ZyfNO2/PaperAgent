# Balanced40 全量审查报告

## 审查范围
- 40 个 case 的 trace（`tmp_re04_eval/balanced40_re10_reflection_fix3/traces/`）
- 检查项：跨 case 污染、Fallback 误标、查询词冗余、ORB-SLAM3 泄漏、论文数分布

## 结果总结

### ✅ 零污染（0/40）
- **跨 case 污染**：0/40 — 所有查询词均与自身主题相关
- **ORB-SLAM3 在非 SLAM case 中**：0/40 — 未在任何非 SLAM case 的 accepted candidates 中发现 ORB-SLAM3
- **Fallback 误标**：0/40 — 没有任何 query 包含 `[Fallback]` 前缀

### ❌ 查询词冗余（7/40）
| Case | 重复模式 | 问题 |
|------|---------|------|
| ENG-THESIS-022 | `steel surface surface defect` | object+task 拼接 |
| ENG-THESIS-028 | `insulator insulator detection` | object+task 拼接 |
| ENG-THESIS-035 | `steel surface surface defect` | object+task 拼接 |
| ENG-THESIS-040 | `insulator insulator fault` | object+task 拼接 |
| ENG-THESIS-074 | `bridge crack crack detection` | object+task 拼接 |
| ENG-THESIS-080 | `concrete crack crack detection` | object+task 拼接 |
| ENG-THESIS-083 | `bridge crack crack segmentation` | object+task 拼接 |

**修复状态**：`_merge_phrases()` 已在 `_axis_query_bases()` 中生效，上述模式将全部去重

### ❌ 论文产量偏低
- 均值：4.4 篇/case（仅来自反射轮次的新论文）
- 分布：
  - 0 篇：0 case
  - 1-2 篇：5 case
  - 3-4 篇：17 case
  - 5-9 篇：17 case
  - 10+篇：1 case
- 低产量 case（≤2）：
  - ENG-THESIS-092：1 篇（离岸风机叶片缺陷检测，小众主题）
  - ENG-THESIS-004：2 篇（YOLOv4 快速检测+测距，主题较窄）
  - ENG-THESIS-051：2 篇（语义 SLAM，DomainScout 离线回退）
  - ENG-THESIS-075：2 篇（混凝土路面裂缝检测，2轮后 new_signal）
  - ENG-THESIS-089：2 篇（道路路面损伤检测，查询词冗余影响）

**根因**：
1. `top_k=3` → 每个查询只返回 3 个结果
2. `_axis_query_bases` 只取 `[:3]` 个 terms，但 `build_round_plan` 每轮只挑 1 个 query/role

**修复**：`top_k=3` → `top_k=5` ✅（已修改 `search_reflection_loop.py`）

### ❌ 其他观察
- ENG-THESIS-100：DomainScout 离线回退导致 `power distribution equipment` 查询返回不相关结果（dirt in paper / airborne power equipment）
- ENG-THESIS-043：UA V 动态目标检测，Round 2 后 ReflectionCritic LLM 失败，改用规则回退
- ENG-THESIS-004：`objects in image or video frames` 作为 object 术语过于泛化

## 已应用的修复

| 文件 | 修改 | 目的 |
|------|------|------|
| `search_reflection_helpers.py` | 新增 `_merge_phrases()` 替换 `f"{a} {b}"` | 消除查询词冗余 |
| `search_reflection_loop.py` | `top_k=3` → `top_k=5`（3 处） | 提高论文产量 |

## 建议的后续步骤

1. **重跑 Balanced40** 验证所有修复效果（约 2 小时）
2. **增加 `per_page` 到 10** 进一步验证论文产量上限
3. **检查 niche topic 的 DomainScout**：ENG-THESIS-092/096 等小众主题的离线回退质量
4. **启动 Loop B/C/D 测试**
