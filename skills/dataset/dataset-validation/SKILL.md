---
name: dataset-validation
description: 数据集证据卡片可用性评分与状态派生 (SOP §4.2). 数据集入池前必经 skill.
metadata:
  type: dataset
  scope: internal
---

# dataset-validation Skill

## 触发条件

- 调用 `apps/api/app/services/scoring.py:score_dataset` 时自动激活
- 数据集 (自动 heuristic 或手动添加) 入 evidence pool 前
- 用户点 "重新评分证据" 按钮时 (rescore)

## 输入结构

```python
dataset: dict = {
    "name": str,
    "scale": str,            # 例: "1800 张 / 6 类"
    "license": str | None,
    "download": str | None,  # URL
    "annotation": str | None,
    "fit": Literal["高", "中", "低", "未知"],
    "source": Literal["public-known", "heuristic"],
}
keywords: dict = {"method_keywords", "task_keywords", "object_keywords", ...}
```

## 输出结构

```python
(score: float, breakdown: dict)  # score ∈ [0, 1]
status: Literal[
    "ready", "needs_preprocess", "needs_permission",
    "weak_match", "unverified", "invalid",
]
```

## 评分规则

```
DatasetScore = 0.20 × existence
             + 0.20 × accessibility
             + 0.15 × annotation_match
             + 0.15 × task_match
             + 0.10 × license_clarity
             + 0.10 × baseline_available
             + 0.10 × scale
```

- `existence`: 名字非空且非"(未匹配公开数据集)" → 1.0
- `accessibility`: 有 download → 1.0; 否则 public-known → 0.6, heuristic → 0.2
- `annotation_match` 受 fit 调整 (高=1.0, 中=0.7, 低=0.3, 未知=0.4)
- `status` 派生规则见 `scoring._derive_dataset_status`

## 禁止事项

- 不要在 score < 0.4 时把 dataset 标 accepted
- 不要在 `name = "(未匹配公开数据集)"` 时给 score > 0.3
- 不要让无 license 的数据集 status="ready"

## 测试样例

- NEU-DET (1800 张 + license + download + 钢材) → score ≈ 0.7, status=ready
- DeepPCB (1500 张 + MIT + download + PCB) → score ≈ 0.75, status=ready
- GC10-DET (3570 张 + 学术使用 + download) → score ≈ 0.7, status=needs_preprocess (license 不明确)
- "(未匹配公开数据集)" → score ≈ 0.1, status=unverified

## 参考

- SOP §4.2 (Plan/PaperAgent_Session05_*.md)
- `apps/api/app/services/scoring.py:136-178`
