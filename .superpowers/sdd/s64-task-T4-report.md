# Phase 64 T4: paper_module_matrix.py — 验收报告

**Task**: Session 64 T4 (Phase 64 — paper/dataset/repo 全链路)

## 产物

- `apps/api/app/services/retrieval/paper_module_matrix.py` (新建, 343 行)
- `apps/api/tests/test_session64_paper_module_matrix.py` (新建, 13 个测试)

## 实现摘要

`PaperModuleMatrix` 把 parallel papers + module papers 拆成 "Base + Module A + Module B + Dataset + Metrics" 五元组, 再按毕业友好度 (公开数据集 / 已知 base / 模块组合数) 排序, 输出 top-5 recommendations.

### 对外接口

```python
def build_module_matrix(
    parallel_papers: list[dict],
    module_papers: list[dict],
    baseline_candidates: list[dict],
    topic_atoms: dict,
) -> PaperModuleMatrix

def _extract_base_modules(paper: dict) -> tuple[str, list[str]]  # (base, [module_a, module_b])
def _rank_combinations(entries: list[PaperModuleEntry]) -> list[dict]
def _generate_recommendations(matrix: PaperModuleMatrix) -> list[dict]
```

`PaperModuleMatrix` schema:
- `topic: str`, `domain: str`
- `entries: list[PaperModuleEntry]` — 每条 paper 的五元组
- `missing_module_types: list[str]` — 缺哪类模块 (attention / loss_function / neck / augmentation / regularization)
- `baseline_options: list[dict]` — 从 baseline_candidates 透传
- `recommended_combinations: list[dict]` — top-5 排序后的组合

### 提取规则 (ponytail: 显式关键词表, 不调用 LLM)

| 字段 | 提取方式 | fallback |
|------|----------|----------|
| `base` | title+abstract 关键词匹配, 按长度倒序 (yolov5 优先于 yolo) | `raw.base` / `raw.framework` / `"unknown"` |
| `module_a` / `module_b` | `_MODULE_KEYWORDS` 表匹配, 最多 2 个 | `raw.modules[:2]` |
| `dataset` | `_DATASET_KEYWORDS` 表匹配 | `raw.dataset` / `"custom/private dataset"` |
| `metrics` | `_METRIC_KEYWORDS` 表匹配 | `raw.metrics` |
| `improvement_description` | `raw.improvement` / `raw.contribution` | 模板: `"Adds X on top of Y..."` |
| `risk_notes` | 启发式: 老论文 + 无 license + 私有数据集 → `data_mismatch` / `reproducibility_low` | 静态规则 |

### 排序打分 (毕业友好度)

```
score = 0
  + 2  if dataset ∈ {COCO, VOC, Cityscapes, ImageNet, MNIST, CIFAR, GLUE, SQuAD, Crack500, DeepCrack, SDNet2018}
  + 1  if base ≠ "unknown" (已知框架)
  + 1  if module_b 非空 (双模块组合)
  - 1  per risk_note
```

按 `(-score, -paper_count)` 降序, 取 top-5. rationale 自动生成: "public benchmark", "well-known base", "two-module combination", "validated by N papers".

### 风险点 / 已知边界

- **关键词表覆盖有限**: 只覆盖 yolo/rcnn/unet/vit/bert 等主流家族, 新框架 (如 RT-DETR / SAM2) 走 fallback. 后续可加 trend 分析时扩表.
- **dataset 提取无歧义消解**: COCO 文本会优先匹配 COCO, 但 "kaggle crack dataset" 会先命中 kaggle. 这是设计选择 (kaggle 算"非公开"信号). 加 scoring 权重后再解决.
- **improvement_description 在无 raw 字段时是模板字符串**: 真实 LLM 抽取可作为后续 phase 的扩展. 当前是 heuristic-only.

## 验证

- import 干净: `from app.services.retrieval.paper_module_matrix import build_module_matrix, PaperModuleMatrix, PaperModuleEntry` → 通过
- self-check (`python paper_module_matrix.py`): 4 entries + 4 recs 全部解析正确
- 单测: `pytest apps/api/tests/test_session64_paper_module_matrix.py -v` → **13 passed**
  - entries 数量 = parallel + module
  - 字段填充 / module_b 可选
  - missing_module_types 识别
  - baseline_options 透传
  - 推荐排序: public dataset 优先
  - 风险标记: 老论文 + 无 license → ≥ 2 个 risk
  - base 提取: yolov5 优先于 yolo
  - 空输入不崩
  - _rank_combinations 去重
  - 提取 metrics
  - top-5 截断

## 后续 (T5+)

T5+ 的 baseline recommender / agent 可直接消费 `matrix.recommended_combinations`, 不必再做提取.
