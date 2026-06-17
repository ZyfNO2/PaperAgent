---
name: paper-card
description: 论文证据卡片评分与分类 (SOP §4.1). 论文检索结果入库前必经 skill.
metadata:
  type: paper
  scope: internal
---

# paper-card Skill

## 触发条件

- 调用 `apps/api/app/services/scoring.py:score_paper_relevance` 时自动激活
- arXiv 检索结果入 evidence pool 前必经
- 用户手动添加论文后, 若缺 relevance_score 也补跑

## 输入结构

```python
paper: dict = {
    "title": str,            # 必填
    "summary": str,          # 摘要 (arXiv 有, heuristic 可能空)
    "year": int | None,
    "authors": list[str],    # 不参与评分, 仅 metadata
}
keywords: dict = {
    "method_keywords": list[str],
    "task_keywords": list[str],
    "object_keywords": list[str],
    "scenario_keywords": list[str],
    "metric_keywords": list[str],
}
```

## 输出结构

```python
(score: float, breakdown: dict)  # score ∈ [0, 1]
paper_type: Literal[
    "survey", "baseline_method", "application",
    "dataset_paper", "benchmark", "case_study",
    "irrelevant", "unknown",
]
```

## 评分规则

```
PaperRelevance = 0.25 × title_match
               + 0.25 × abstract_match
               + 0.15 × task_match
               + 0.15 × object_match
               + 0.10 × method_match
               + 0.10 × recency
```

- `*_match`: 0~1, 关键词与文本的 token 重合度 (|text ∩ words| / |words|)
- `recency`: ≤3 年=1.0, ≤6=0.6, ≤10=0.3, 更老=0.1, 未知=0.3
- type 分类: 按 SOP §4.1 优先级, 标题/摘要启发式关键字
- `irrelevant` 直接过滤不入核心证据池 (SOP §4.4 验收)

## 禁止事项

- 不要用 LLM 评分 (Session 5 范围内不允许, 速度/可复现性都不达标)
- 不要把 LLM 分类结果覆盖到 `paper_type` (heuristic 已够用)
- 不要在 score < 0.3 时把论文标 accepted (留给用户决定)

## 测试样例

- "YOLOv8 steel surface defect detection" → relevance ≈ 0.7, type=baseline_method
- "Survey on defect detection methods" → type=survey
- "German Open-Ended Survey" (与 PINN 无关) → relevance ≈ 0.05, type=irrelevant

## 参考

- SOP §4.1 (Plan/PaperAgent_Session05_*.md)
- `apps/api/app/services/scoring.py:72-103`
- 启发式来源: Academic Research Skills / Claude Scholar (不直接照搬, 重写)
